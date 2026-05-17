from __future__ import annotations

import random
from collections.abc import Iterable

from dangosim.core.models import DeviceType, EventRecord, MoveResult, RaceConfig, RaceSnapshot


class RaceSimulator:
    def __init__(self, config: RaceConfig) -> None:
        self.config = config
        self._rng = random.Random(config.seed)
        self._positions = {dango.id: dango.start_position for dango in config.dangos}
        self._dangos = {dango.id: dango for dango in config.dangos}
        self._stacks = {position: [] for position in range(1, config.track.length + 1)}
        for dango in config.dangos:
            self._stacks[dango.start_position].append(dango.id)
        # Initial co-location is not treated as a landed stack until pieces move.
        self._stack_active: set[str] = set()
        self._event_log: list[EventRecord] = []
        self._rankings: list[str] = []
        self._finished = False
        self._used_once_abilities: set[tuple[str, str]] = set()

    def step_dango(self, dango_id: str, roll: int) -> MoveResult:
        if dango_id not in self._dangos:
            raise KeyError(f"Unknown dango id: {dango_id}")
        if roll < 0:
            raise ValueError("Roll must be non-negative.")

        dango = self._dangos[dango_id]
        from_position = self._positions[dango_id]
        effective_roll, ability_reasons = self._apply_before_move_abilities(dango_id, roll)
        carried = self._take_moving_group(dango_id, from_position)
        base_position = self._move_position(from_position, self._forward_delta(dango_id) * effective_roll, dango_id)
        device = self.config.track.device_at(base_position)
        to_position = self._apply_device(base_position, device, dango_id)

        self._place_group(to_position, carried)
        reasons: list[str] = list(ability_reasons)
        if device is DeviceType.TIME_RIFT:
            self._open_time_rift(to_position)
            reasons.append("time_rift")
        elif device is not DeviceType.BLANK:
            reasons.append(f"device:{device.value}")
            self._event_log.append(
                EventRecord(
                    event_type="device",
                    message=f"{dango.name} 觸發 {device.value}",
                    data={"dango_id": dango_id, "position": base_position, "device": device.value},
                )
            )

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
        active = [dango_id for dango_id in self._positions if dango_id not in self._rankings]
        if not active:
            raise RuntimeError("Race has no active dangos.")
        dango_id = self._rng.choice(active)
        max_roll = 6 if self._dangos[dango_id].is_boss else 3
        return self.step_dango(dango_id, self._rng.randint(1, max_roll))

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
            finished=self._finished,
        )

    def _take_moving_group(self, dango_id: str, position: int) -> list[str]:
        stack = self._stacks[position]
        index = stack.index(dango_id)
        if dango_id not in self._stack_active:
            group = [dango_id]
            del stack[index]
            return group
        group = stack[index:]
        del stack[index:]
        return group

    def _place_group(self, position: int, group: Iterable[str]) -> None:
        placed = list(group)
        self._stacks[position].extend(placed)
        for dango_id in placed:
            self._positions[dango_id] = position
            self._stack_active.add(dango_id)
        for dango_id in self._stacks[position]:
            self._stack_active.add(dango_id)

    def _forward_delta(self, dango_id: str) -> int:
        return -1 if self._dangos[dango_id].is_boss else 1

    def _apply_before_move_abilities(self, dango_id: str, roll: int) -> tuple[int, tuple[str, ...]]:
        dango = self._dangos[dango_id]
        effective_roll = roll
        reasons: list[str] = []
        for ability in dango.abilities:
            key = (dango_id, ability.id)
            if ability.trigger != "before_move":
                continue
            if ability.once_per_race and key in self._used_once_abilities:
                continue
            if not all(condition.type == "always" for condition in ability.conditions):
                continue
            if self._rng.random() > ability.probability:
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
                    message=f"{dango.name} 發動能力 {ability.id}。",
                    data={"dango_id": dango_id, "ability_id": ability.id},
                )
            )
        return effective_roll, tuple(reasons)

    def _move_position(self, position: int, delta: int, dango_id: str) -> int:
        target = position + delta
        if self._dangos[dango_id].is_boss:
            return self._wrap_position(target)
        return min(self.config.track.finish, max(1, target))

    def _wrap_position(self, position: int) -> int:
        length = self.config.track.length
        return ((position - 1) % length) + 1

    def _apply_device(self, position: int, device: DeviceType, dango_id: str) -> int:
        if device in (DeviceType.BLANK, DeviceType.TIME_RIFT):
            return position

        forward = self._forward_delta(dango_id)
        is_boss = self._dangos[dango_id].is_boss
        if device is DeviceType.ADVANCE:
            delta = -forward if is_boss else forward
        elif device is DeviceType.BLOCK:
            delta = forward if is_boss else -forward
        else:
            delta = 0
        return self._move_position(position, delta, dango_id)

    def _open_time_rift(self, position: int) -> None:
        stack = self._stacks[position]
        self._rng.shuffle(stack)
        self._event_log.append(
            EventRecord(
                event_type="time_rift",
                message="時空裂隙打開，堆疊順序被重排。",
                data={"position": position, "stack": list(stack)},
            )
        )

    def _record_finishers(self) -> None:
        for dango_id, position in list(self._positions.items()):
            dango = self._dangos[dango_id]
            ranked = dango.ranked or (dango.is_boss and self.config.boss_ranked)
            if not ranked or dango_id in self._rankings:
                continue
            if not dango.is_boss and position >= self.config.track.finish:
                self._rankings.append(dango_id)
                self._event_log.append(
                    EventRecord("finish", f"{dango.name} 抵達終點。", {"dango_id": dango_id})
                )
        ranked_count = sum(
            1 for dango in self._dangos.values() if dango.ranked or (dango.is_boss and self.config.boss_ranked)
        )
        self._finished = ranked_count > 0 and len(self._rankings) >= ranked_count
