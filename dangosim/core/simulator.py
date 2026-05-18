from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass

from dangosim.core.boss_rules import should_boss_return_to_finish
from dangosim.core.models import AbilityConfig, DeviceType, EventRecord, MoveResult, RaceConfig, RaceSnapshot


_DEVICE_DISPLAY_NAMES = {
    DeviceType.BLANK: "空白",
    DeviceType.ADVANCE: "推進裝置",
    DeviceType.BLOCK: "阻遏裝置",
    DeviceType.TIME_RIFT: "時空裂隙",
}


@dataclass(frozen=True)
class _BuiltinBeforeMoveResult:
    steps: int
    skip_movement: bool = False
    triggered: bool = False


@dataclass(frozen=True)
class _BeforeMoveResult:
    steps: int
    reasons: tuple[str, ...]
    skip_movement: bool = False


class RaceSimulator:
    def __init__(self, config: RaceConfig) -> None:
        self.config = config
        self._rng = random.Random(config.seed)
        self._positions = {dango.id: dango.start_position for dango in config.dangos}
        self._dangos = {dango.id: dango for dango in config.dangos}
        self._stacks = {position: [] for position in range(1, config.track.length + 1)}
        for dango in config.dangos:
            self._stacks[dango.start_position].append(dango.id)
        for stack in self._stacks.values():
            self._shuffle_stack_preserving_boss_bottom(stack, self.config.initial_stack_order)
        # Initial co-location is visible as randomized stack order, but is not
        # treated as a carried stack until pieces move.
        self._stack_active: set[str] = set()
        self._event_log: list[EventRecord] = []
        self._rankings: list[str] = []
        self._finished = False
        self._used_once_abilities: set[tuple[str, str]] = set()
        self._turn_queue: list[str] = []
        self._round_order: list[str] = []
        self._round_number = 0
        self._last_rolls: dict[str, int] = {}
        self._round_rolls: dict[str, int] = {}
        self._fixed_roll_indices: dict[str, int] = {}
        self._ability_flags: dict[str, set[str]] = {dango.id: set() for dango in config.dangos}
        self._round_step_penalties: dict[str, int] = {}
        self._round_start_bottom_dangos: set[str] = set()
        self._skip_turn_dangos: set[str] = set()
        self._last_action_next_round: set[str] = set()

    def step_dango(self, dango_id: str, roll: int) -> MoveResult:
        if dango_id not in self._dangos:
            raise KeyError(f"Unknown dango id: {dango_id}")
        if roll < 0:
            raise ValueError("Roll must be non-negative.")

        dango = self._dangos[dango_id]
        from_position = self._positions[dango_id]
        before_move = self._apply_before_move_abilities(dango_id, roll)
        if before_move.skip_movement:
            self._last_rolls[dango_id] = roll
            self._record_finishers()
            return MoveResult(
                dango_id=dango_id,
                roll=roll,
                from_position=from_position,
                to_position=from_position,
                carried=(),
                device_triggered=DeviceType.BLANK,
                reasons=before_move.reasons,
            )

        effective_roll = before_move.steps
        ability_reasons = before_move.reasons
        carried = self._take_moving_group(dango_id, from_position)
        base_delta = self._forward_delta(dango_id) * effective_roll
        base_position = self._move_position(from_position, base_delta, dango_id)
        if dango.is_boss:
            self._collect_boss_passed_dangos(carried, self._movement_path(from_position, base_delta, dango_id))
        device = self.config.track.device_at(base_position)
        device_delta = self._device_delta(device, dango_id)
        to_position = self._move_position(base_position, device_delta, dango_id)
        if dango.is_boss:
            self._collect_boss_passed_dangos(carried, self._movement_path(base_position, device_delta, dango_id))

        self._place_group(to_position, carried)
        self._update_boss_meeting_flags()
        reasons: list[str] = list(ability_reasons)
        if device is DeviceType.TIME_RIFT:
            self._open_time_rift(to_position)
            reasons.append("time_rift")
        elif device is not DeviceType.BLANK:
            reasons.append(f"device:{device.value}")
            self._event_log.append(
                EventRecord(
                    event_type="device",
                    message=f"{dango.name} 觸發 {self._device_display_name(device)}",
                    data={"dango_id": dango_id, "position": base_position, "device": device.value},
                )
            )

        self._apply_after_move_abilities(dango_id, from_position)
        self._last_rolls[dango_id] = roll
        self._record_finishers()
        return MoveResult(
            dango_id=dango_id,
            roll=roll,
            from_position=from_position,
            to_position=to_position,
            carried=tuple(carried),
            device_triggered=device,
            reasons=tuple(reasons),
        )

    def step_next(self) -> MoveResult:
        dango_id = self._next_actor()
        had_precomputed_roll = dango_id in self._round_rolls
        roll = self._round_rolls[dango_id] if had_precomputed_roll else self._roll_for(dango_id)
        result = self.step_dango(dango_id, roll)
        if not self._turn_queue:
            self._finish_round()
        return result

    def run_until_finished(self, max_steps: int = 1000) -> RaceSnapshot:
        for _ in range(max_steps):
            if self._finished:
                return self.snapshot()
            self.step_next()
        raise RuntimeError(f"Race did not finish within {max_steps} steps.")

    def snapshot(self) -> RaceSnapshot:
        return RaceSnapshot(
            positions=dict(self._positions),
            stacks={position: list(stack) for position, stack in self._stacks.items() if stack},
            event_log=tuple(self._event_log),
            rankings=tuple(self._rankings),
            live_rankings=self._live_rankings(),
            round_number=self._round_number,
            finished=self._finished,
            round_order=tuple(self._round_order),
            round_rolls=dict(self._round_rolls),
            remaining_round_order=tuple(self._turn_queue),
        )

    def _take_moving_group(self, dango_id: str, position: int) -> list[str]:
        stack = self._stacks[position]
        index = stack.index(dango_id)
        if self._dangos[dango_id].is_boss:
            group = stack[index:]
            del stack[index:]
            return group
        if dango_id not in self._stack_active:
            group = [dango_id]
            del stack[index]
            return group
        group = stack[index:]
        del stack[index:]
        return group

    def _next_actor(self) -> str:
        while True:
            if not self._turn_queue:
                self._start_round()
            if not self._turn_queue:
                raise RuntimeError("Race has no active dangos.")
            dango_id = self._turn_queue.pop(0)
            if dango_id not in self._rankings:
                return dango_id

    def _start_round(self) -> None:
        next_round = self._round_number + 1
        active = [
            dango_id
            for dango_id in self._positions
            if dango_id not in self._rankings and self._can_act_in_round(dango_id, next_round)
        ]
        if not active:
            self._turn_queue = []
            self._round_order = []
            self._round_rolls = {}
            self._round_start_bottom_dangos = set()
            return
        pending_move_last = set(self._last_action_next_round)
        self._last_action_next_round.difference_update(pending_move_last)
        self._round_number += 1
        self._round_start_bottom_dangos = {
            dango_id for dango_id in active if self._is_bottom_of_stack(dango_id)
        }
        self._round_step_penalties = {}
        self._skip_turn_dangos = set()
        self._apply_round_start_abilities()
        self._rng.shuffle(active)
        if next_round == 1:
            active = self._apply_order_override(active, self.config.first_round_order)
        move_last = [dango_id for dango_id in active if dango_id in pending_move_last]
        if move_last:
            active = [dango_id for dango_id in active if dango_id not in pending_move_last] + move_last
        self._turn_queue = active
        self._round_order = list(active)
        self._event_log.append(
            EventRecord(
                event_type="round_start",
                message=f"第 {self._round_number} 回合行動順序：" + "、".join(self._dango_names(active)),
                data={"round": self._round_number, "order": list(active)},
            )
        )
        self._round_rolls = {dango_id: self._roll_for(dango_id) for dango_id in active}
        self._apply_after_roll_abilities(active)

    def _can_act_in_round(self, dango_id: str, round_number: int) -> bool:
        dango = self._dangos[dango_id]
        return not dango.is_boss or round_number >= 3

    def _finish_round(self) -> None:
        if self._round_number < 3:
            return
        regular_positions = self._regular_positions()
        if not regular_positions:
            return
        for boss_id, boss in self._dangos.items():
            if not boss.is_boss or boss_id in self._rankings:
                continue
            if should_boss_return_to_finish(
                boss_position=self._positions[boss_id],
                finish=self.config.track.finish,
                length=self.config.track.length,
                regular_positions=regular_positions,
            ):
                self._return_boss_to_finish(boss_id)

    def _regular_positions(self) -> tuple[int, ...]:
        return tuple(
            position
            for dango_id, position in self._positions.items()
            if not self._dangos[dango_id].is_boss and dango_id not in self._rankings
        )

    def _return_boss_to_finish(self, boss_id: str) -> None:
        finish = self.config.track.finish
        old_position = self._positions[boss_id]
        if old_position == finish:
            return
        self._stacks[old_position].remove(boss_id)
        self._place_group(finish, [boss_id])
        self._event_log.append(
            EventRecord(
                event_type="boss_return",
                message=f"{self._dangos[boss_id].name} 前進方向到終點間已無團子，傳送回終點。",
                data={"dango_id": boss_id, "from_position": old_position, "to_position": finish},
            )
        )

    def _place_group(self, position: int, group: Iterable[str]) -> None:
        placed = list(group)
        bosses = [dango_id for dango_id in placed if self._dangos[dango_id].is_boss]
        regulars = [dango_id for dango_id in placed if not self._dangos[dango_id].is_boss]
        self._stacks[position][0:0] = bosses
        self._stacks[position].extend(regulars)
        for dango_id in placed:
            self._positions[dango_id] = position
            self._stack_active.add(dango_id)
        for dango_id in self._stacks[position]:
            self._stack_active.add(dango_id)

    def _roll_for(self, dango_id: str) -> int:
        if self._has_ability(dango_id, "moning_precision_calculation"):
            roll_cycle = (3, 2, 1)
            index = self._fixed_roll_indices.get(dango_id, 0)
            self._fixed_roll_indices[dango_id] = index + 1
            return roll_cycle[index % len(roll_cycle)]
        if self._has_ability(dango_id, "shorekeeper_future"):
            return self._rng.choice([2, 3])
        max_roll = 6 if self._dangos[dango_id].is_boss else 3
        return self._rng.randint(1, max_roll)

    def _forward_delta(self, dango_id: str) -> int:
        return -1 if self._dangos[dango_id].is_boss else 1

    def _apply_before_move_abilities(self, dango_id: str, roll: int) -> _BeforeMoveResult:
        dango = self._dangos[dango_id]
        if dango_id in self._skip_turn_dangos:
            ability = self._ability_by_id(dango_id, "augusta_governor_authority")
            ability_name = ability.name if ability else "總督權柄"
            self._skip_turn_dangos.remove(dango_id)
            self._event_log.append(
                EventRecord(
                    event_type="ability",
                    message=f"{dango.name} 發動能力 {ability_name}，本回合不行動。",
                    data={
                        "dango_id": dango_id,
                        "ability_id": "augusta_governor_authority",
                        "ability_name": ability_name,
                    },
                )
            )
            return _BeforeMoveResult(
                steps=roll,
                reasons=("ability:augusta_governor_authority",),
                skip_movement=True,
            )
        effective_roll = roll
        skip_movement = False
        reasons: list[str] = []
        for ability in dango.abilities:
            key = (dango_id, ability.id)
            if ability.trigger != "before_move":
                continue
            if ability.once_per_race and key in self._used_once_abilities:
                continue
            if not all(condition.type == "always" for condition in ability.conditions):
                continue
            if self._is_builtin_action(ability):
                result = self._apply_builtin_before_move(dango_id, ability, effective_roll)
                if result.steps == effective_roll and not result.skip_movement and not result.triggered:
                    continue
                effective_roll = result.steps
                skip_movement = skip_movement or result.skip_movement
                if ability.once_per_race:
                    self._used_once_abilities.add(key)
                reasons.append(f"ability:{ability.id}")
                self._event_log.append(
                    EventRecord(
                        event_type="ability",
                        message=f"{dango.name} 發動能力 {ability.name}。",
                        data={"dango_id": dango_id, "ability_id": ability.id, "ability_name": ability.name},
                    )
                )
                continue
            if self._rng.random() >= ability.probability:
                continue
            for action in ability.actions:
                if action.type == "add_steps":
                    effective_roll += int(action.value or 0)
            if ability.once_per_race:
                self._used_once_abilities.add(key)
            reasons.append(f"ability:{ability.id}")
            self._event_log.append(
                EventRecord(
                    event_type="ability",
                    message=f"{dango.name} 發動能力 {ability.name}。",
                    data={"dango_id": dango_id, "ability_id": ability.id, "ability_name": ability.name},
                )
            )
        penalty = self._round_step_penalties.get(dango_id, 0)
        if penalty and not skip_movement:
            effective_roll = max(1, effective_roll - penalty)
            reasons.append("round_penalty")
        return _BeforeMoveResult(
            steps=effective_roll,
            reasons=tuple(reasons),
            skip_movement=skip_movement,
        )

    def _apply_builtin_before_move(self, dango_id: str, ability, roll: int) -> _BuiltinBeforeMoveResult:
        if ability.id == "daphne_same_roll_bonus":
            return _BuiltinBeforeMoveResult(roll + 2 if self._last_rolls.get(dango_id) == roll else roll)
        if ability.id == "snow_bird":
            return _BuiltinBeforeMoveResult(roll + 1 if "met_boss" in self._ability_flags[dango_id] else roll)
        if ability.id == "floro_bottom_bonus":
            return _BuiltinBeforeMoveResult(roll + 3 if dango_id in self._round_start_bottom_dangos else roll)
        if ability.id == "kat_late_surge_bonus":
            if "kat_late_surge_active" in self._ability_flags[dango_id] and self._rng.random() < ability.probability:
                return _BuiltinBeforeMoveResult(roll + 2)
            return _BuiltinBeforeMoveResult(roll)
        if ability.id in {"phoebe_blessing", "phoebe_bonus"}:
            return _BuiltinBeforeMoveResult(roll + 1 if self._rng.random() < ability.probability else roll)
        if ability.id == "chisaki_threshold_analysis":
            if dango_id not in self._round_rolls:
                return _BuiltinBeforeMoveResult(roll)
            round_rolls = self._round_rolls.values()
            min_roll = min(round_rolls)
            return _BuiltinBeforeMoveResult(roll + 2 if roll == min_roll else roll)
        if ability.id == "colletta_double_authority":
            return _BuiltinBeforeMoveResult(roll * 2 if self._rng.random() < ability.probability else roll)
        if ability.id == "linne_colorful":
            chance = self._rng.random()
            if chance < 0.2:
                return _BuiltinBeforeMoveResult(0, skip_movement=True)
            if chance < 0.8:
                return _BuiltinBeforeMoveResult(roll * 2)
            return _BuiltinBeforeMoveResult(roll)
        if ability.id == "jinhsi_magistrate_name":
            if self._has_stacked_above(dango_id) and self._rng.random() < ability.probability:
                self._move_to_stack_top(dango_id)
                return _BuiltinBeforeMoveResult(roll, triggered=True)
            return _BuiltinBeforeMoveResult(roll)
        if ability.id == "calcharo_shadow_follow":
            return _BuiltinBeforeMoveResult(roll + 3 if self._is_last_regular(dango_id) else roll)
        return _BuiltinBeforeMoveResult(roll)

    def _apply_after_move_abilities(self, dango_id: str, from_position: int) -> None:
        for ability in self._dangos[dango_id].abilities:
            key = (dango_id, ability.id)
            if ability.trigger != "after_move" or not self._is_builtin_action(ability):
                continue
            if ability.once_per_race and key in self._used_once_abilities:
                continue
            if ability.id == "kat_activate_late_surge" and self._is_last_regular(dango_id):
                self._ability_flags[dango_id].add("kat_late_surge_active")
                self._used_once_abilities.add(key)
                self._event_log.append(
                    EventRecord(
                        event_type="ability",
                        message=f"{self._dangos[dango_id].name} 進入追趕狀態。",
                        data={"dango_id": dango_id, "ability_id": ability.id, "ability_name": ability.name},
                    )
                )
            elif ability.id == "aemiss_ghost" and self._crossed_midpoint(from_position, self._positions[dango_id]):
                target = self._nearest_regular_ahead(dango_id)
                if target is None:
                    continue
                self._move_single_to_position(dango_id, self._positions[target])
                self._used_once_abilities.add(key)
                self._event_log.append(
                    EventRecord(
                        event_type="ability",
                        message=f"{self._dangos[dango_id].name} 傳送到最近團子頂端。",
                        data={"dango_id": dango_id, "ability_id": ability.id, "ability_name": ability.name, "target": target},
                    )
                )
            elif ability.id == "yuno_anchor_fate" and self._crossed_midpoint(from_position, self._positions[dango_id]):
                targets = self._adjacent_regular_rank_targets(dango_id)
                if not targets:
                    continue
                self._move_ranked_targets_to_position(targets, self._positions[dango_id])
                self._used_once_abilities.add(key)
                self._event_log.append(
                    EventRecord(
                        event_type="ability",
                        message=f"{self._dangos[dango_id].name} 發動能力 {ability.name}，錨定前後團子。",
                        data={
                            "dango_id": dango_id,
                            "ability_id": ability.id,
                            "ability_name": ability.name,
                            "targets": list(targets),
                        },
                    )
                )

    def _move_position(self, position: int, delta: int, dango_id: str) -> int:
        target = position + delta
        if self._dangos[dango_id].is_boss:
            return self._wrap_position(target)
        return min(self.config.track.finish, max(1, target))

    def _movement_path(self, position: int, delta: int, dango_id: str) -> tuple[int, ...]:
        if delta == 0:
            return ()
        step = 1 if delta > 0 else -1
        current = position
        path: list[int] = []
        for _ in range(abs(delta)):
            current = self._move_position(current, step, dango_id)
            path.append(current)
            if not self._dangos[dango_id].is_boss and current in (1, self.config.track.finish):
                break
        return tuple(path)

    def _collect_boss_passed_dangos(self, carried: list[str], path: Iterable[int]) -> None:
        if not carried or not self._dangos[carried[0]].is_boss:
            return
        for position in path:
            stack = self._stacks[position]
            picked = [dango_id for dango_id in stack if not self._dangos[dango_id].is_boss]
            if not picked:
                continue
            self._stacks[position] = [dango_id for dango_id in stack if self._dangos[dango_id].is_boss]
            carried[1:1] = picked

    def _wrap_position(self, position: int) -> int:
        length = self.config.track.length
        return ((position - 1) % length) + 1

    def _apply_device(self, position: int, device: DeviceType, dango_id: str) -> int:
        return self._move_position(position, self._device_delta(device, dango_id), dango_id)

    def _device_delta(self, device: DeviceType, dango_id: str) -> int:
        if device in (DeviceType.BLANK, DeviceType.TIME_RIFT):
            return 0

        forward = self._forward_delta(dango_id)
        is_boss = self._dangos[dango_id].is_boss
        if device is DeviceType.ADVANCE:
            delta = -forward if is_boss else forward
        elif device is DeviceType.BLOCK:
            delta = forward if is_boss else -forward
        else:
            delta = 0
        delta += self._device_ability_delta(dango_id, device, forward)
        return delta

    def _device_ability_delta(self, dango_id: str, device: DeviceType, forward: int) -> int:
        if not self._has_ability(dango_id, "lu_device_master"):
            return 0
        if device is DeviceType.ADVANCE:
            return forward * 3
        if device is DeviceType.BLOCK:
            return -forward
        return 0

    def _open_time_rift(self, position: int) -> None:
        stack = self._stacks[position]
        self._shuffle_stack_preserving_boss_bottom(stack)
        self._event_log.append(
            EventRecord(
                event_type="time_rift",
                message="時空裂隙打開，堆疊順序被重排。",
                data={"position": position, "stack": list(stack)},
            )
        )

    def _shuffle_stack_preserving_boss_bottom(self, stack: list[str], order_override=None) -> None:
        if len(stack) < 2:
            return
        bosses = [dango_id for dango_id in stack if self._dangos[dango_id].is_boss]
        regulars = [dango_id for dango_id in stack if not self._dangos[dango_id].is_boss]
        self._rng.shuffle(regulars)
        regulars = self._apply_order_override(regulars, order_override or {})
        stack[:] = bosses + regulars

    def _apply_order_override(self, dango_ids: list[str], order_override) -> list[str]:
        if not order_override:
            return dango_ids
        specified = [dango_id for dango_id in dango_ids if dango_id in order_override]
        unspecified = [dango_id for dango_id in dango_ids if dango_id not in order_override]
        specified.sort(key=lambda dango_id: order_override[dango_id])
        return specified + unspecified

    def _record_finishers(self) -> None:
        if self._finished:
            return
        ranked_ids = self._ranked_participant_ids()
        finishers = [
            dango_id
            for dango_id, position in self._positions.items()
            if dango_id in ranked_ids
            and not self._dangos[dango_id].is_boss
            and position >= self.config.track.finish
        ]
        if not finishers:
            return

        self._rankings = list(self._live_rankings())
        self._finished = True
        for dango_id in finishers:
            self._event_log.append(
                EventRecord("finish", f"{self._dangos[dango_id].name} 抵達終點。", {"dango_id": dango_id})
            )
        if self._rankings:
            winner = self._rankings[0]
            self._event_log.append(
                EventRecord(
                    event_type="race_finish",
                    message=f"比賽結束，{self._dangos[winner].name} 取得第 1 名。",
                    data={"rankings": list(self._rankings)},
                )
            )

    def _apply_round_start_abilities(self) -> None:
        for dango_id in list(self._positions):
            if dango_id in self._rankings:
                continue
            augusta = self._ability_by_id(dango_id, "augusta_governor_authority")
            if augusta and self._is_top_of_stack(dango_id):
                self._skip_turn_dangos.add(dango_id)
                self._last_action_next_round.add(dango_id)
                self._event_log.append(
                    EventRecord(
                        event_type="ability",
                        message=f"{self._dangos[dango_id].name} 發動能力 {augusta.name}，下回合最後行動。",
                        data={"dango_id": dango_id, "ability_id": augusta.id, "ability_name": augusta.name},
                    )
                )

            changli = self._ability_by_id(dango_id, "changli_strategic_delay")
            if changli and self._has_stacked_below(dango_id) and self._rng.random() < changli.probability:
                self._last_action_next_round.add(dango_id)
                self._event_log.append(
                    EventRecord(
                        event_type="ability",
                        message=f"{self._dangos[dango_id].name} 發動能力 {changli.name}，下回合最後行動。",
                        data={"dango_id": dango_id, "ability_id": changli.id, "ability_name": changli.name},
                    )
                )

    def _apply_after_roll_abilities(self, active: Iterable[str]) -> None:
        active_ids = set(active)
        ranked = self._regulars_by_progress()
        for dango_id in list(self._positions):
            if dango_id not in active_ids:
                continue
            ability = self._ability_by_id(dango_id, "sigurd_sun_help")
            if ability is None or ability.trigger != "after_roll" or dango_id not in ranked:
                continue
            index = ranked.index(dango_id)
            targets = ranked[max(0, index - 2) : index]
            for target in targets:
                self._round_step_penalties[target] = max(self._round_step_penalties.get(target, 0), 1)
            if targets:
                self._event_log.append(
                    EventRecord(
                        event_type="ability",
                        message=f"{self._dangos[dango_id].name} 標記前方團子：" + "、".join(self._dango_names(targets)),
                        data={"dango_id": dango_id, "targets": list(targets), "ability_id": ability.id, "ability_name": ability.name},
                    )
                )

    def _regulars_by_progress(self) -> list[str]:
        regular_ids = {
            dango_id
            for dango_id in self._positions
            if not self._dangos[dango_id].is_boss and dango_id not in self._rankings
        }
        return list(self._ordered_by_progress(regular_ids))

    def _ranked_participant_ids(self) -> set[str]:
        return {dango_id for dango_id in self._dangos if self._is_ranked_participant(dango_id)}

    def _is_ranked_participant(self, dango_id: str) -> bool:
        dango = self._dangos[dango_id]
        if dango.is_boss:
            return self.config.boss_ranked and self._can_act_in_round(dango_id, self._round_number)
        return dango.ranked

    def _live_rankings(self) -> tuple[str, ...]:
        return self._ordered_by_progress(self._ranked_participant_ids())

    def _ordered_by_progress(self, dango_ids: set[str]) -> tuple[str, ...]:
        if not dango_ids:
            return ()
        ordered: list[str] = []
        ordered_positions = sorted(
            {position for dango_id, position in self._positions.items() if dango_id in dango_ids},
            reverse=True,
        )
        for position in ordered_positions:
            stack = self._stacks.get(position, [])
            for dango_id in reversed(stack):
                if dango_id in dango_ids:
                    ordered.append(dango_id)
            missing_from_stack = sorted(
                dango_id
                for dango_id in dango_ids
                if self._positions[dango_id] == position and dango_id not in stack
            )
            ordered.extend(missing_from_stack)
        return tuple(ordered)

    def _update_boss_meeting_flags(self) -> None:
        boss_positions = {
            position for dango_id, position in self._positions.items() if self._dangos[dango_id].is_boss
        }
        for dango_id, position in self._positions.items():
            if self._has_ability(dango_id, "snow_bird") and position in boss_positions:
                self._ability_flags[dango_id].add("met_boss")

    def _has_ability(self, dango_id: str, ability_id: str) -> bool:
        return any(ability.id == ability_id for ability in self._dangos[dango_id].abilities)

    def _ability_by_id(self, dango_id: str, ability_id: str) -> AbilityConfig | None:
        for ability in self._dangos[dango_id].abilities:
            if ability.id == ability_id:
                return ability
        return None

    def _is_builtin_action(self, ability) -> bool:
        return any(action.type == "builtin" for action in ability.actions)

    def _is_bottom_of_stack(self, dango_id: str) -> bool:
        position = self._positions[dango_id]
        stack = self._stacks[position]
        return len(stack) >= 2 and stack[0] == dango_id

    def _is_top_of_stack(self, dango_id: str) -> bool:
        position = self._positions[dango_id]
        stack = self._stacks[position]
        return len(stack) >= 2 and stack[-1] == dango_id

    def _has_stacked_below(self, dango_id: str) -> bool:
        position = self._positions[dango_id]
        stack = self._stacks[position]
        return len(stack) >= 2 and stack.index(dango_id) > 0

    def _has_stacked_above(self, dango_id: str) -> bool:
        position = self._positions[dango_id]
        stack = self._stacks[position]
        return len(stack) >= 2 and stack.index(dango_id) < len(stack) - 1

    def _is_last_regular(self, dango_id: str) -> bool:
        if self._dangos[dango_id].is_boss or dango_id in self._rankings:
            return False
        regulars = self._regulars_by_progress()
        return bool(regulars) and regulars[-1] == dango_id

    def _crossed_midpoint(self, from_position: int, to_position: int) -> bool:
        midpoint = self.config.track.midpoint
        return from_position <= midpoint < to_position

    def _nearest_regular_ahead(self, dango_id: str) -> str | None:
        position = self._positions[dango_id]
        candidates = [
            candidate_id
            for candidate_id, candidate_position in self._positions.items()
            if candidate_id != dango_id
            and not self._dangos[candidate_id].is_boss
            and candidate_id not in self._rankings
            and candidate_position > position
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda candidate_id: self._positions[candidate_id])

    def _move_single_to_position(self, dango_id: str, position: int) -> None:
        old_position = self._positions[dango_id]
        self._stacks[old_position].remove(dango_id)
        self._place_group(position, [dango_id])

    def _move_to_stack_top(self, dango_id: str) -> None:
        position = self._positions[dango_id]
        stack = self._stacks[position]
        stack.remove(dango_id)
        stack.append(dango_id)

    def _adjacent_regular_rank_targets(self, dango_id: str) -> tuple[str, ...]:
        ranked = self._regulars_by_progress()
        if dango_id not in ranked:
            return ()
        index = ranked.index(dango_id)
        targets: list[str] = []
        if index > 0:
            targets.append(ranked[index - 1])
        if index + 1 < len(ranked):
            targets.append(ranked[index + 1])
        return tuple(targets)

    def _move_ranked_targets_to_position(self, targets: tuple[str, ...], position: int) -> None:
        for target in targets:
            old_position = self._positions[target]
            self._stacks[old_position].remove(target)
        # `_place_group` appends regulars bottom-to-top, so reverse the ranked
        # order to keep the highest-ranked teleported dango visually on top.
        self._place_group(position, reversed(targets))

    def _dango_names(self, dango_ids: Iterable[str]) -> list[str]:
        return [self._dangos[dango_id].name for dango_id in dango_ids]

    def _device_display_name(self, device: DeviceType) -> str:
        return _DEVICE_DISPLAY_NAMES.get(device, device.value)
