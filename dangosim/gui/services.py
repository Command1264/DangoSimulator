from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from dangosim.core.batch import simulate_many
from dangosim.core.models import MoveResult, RaceConfig, RaceSnapshot
from dangosim.core.simulator import RaceSimulator
from dangosim.gui.view_models import (
    RaceViewState,
    RankingViewRow,
    SimulationResultRow,
    avatar_label_for_name,
    rank_simulation_rows,
)
from dangosim.randomness import SeedMode, resolve_seed


@dataclass(frozen=True)
class BatchSimulationResult:
    rows: list[SimulationResultRow]
    seed_mode: SeedMode
    seed: int
    completed_runs: int
    total_runs: int
    cancelled: bool


class GuiRaceController:
    def __init__(self, config: RaceConfig) -> None:
        self._config = config
        self._simulator = RaceSimulator(config)
        self._last_move: MoveResult | None = None

    def reset(self) -> RaceViewState:
        self._simulator = RaceSimulator(self._config)
        self._last_move = None
        return self.view_state()

    def step(self) -> RaceViewState:
        if self.view_state().finished:
            return self.view_state()
        self._last_move = self._simulator.step_next()
        return self.view_state()

    def view_state(self) -> RaceViewState:
        return _view_state_from_snapshot(
            self._simulator.snapshot(),
            config=self._config,
            last_move=self._last_move,
        )


def run_batch_simulation(
    config: RaceConfig,
    *,
    runs: int,
    seed: int | None,
    seed_mode: SeedMode = SeedMode.FIXED,
    progress_callback: Callable[[int, int], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
    workers: int | str | None = 1,
) -> BatchSimulationResult:
    resolved_seed = resolve_seed(mode=seed_mode, requested_seed=seed, config_seed=config.seed)
    summary = simulate_many(
        replace(config, seed=resolved_seed.seed),
        runs=runs,
        seed=resolved_seed.seed,
        seed_mode=resolved_seed.mode,
        progress_callback=progress_callback,
        cancel_requested=cancel_requested,
        workers=workers,
    )
    rows = [
        SimulationResultRow(
            dango_id=str(item["dango_id"]),
            name=str(item["name"]),
            wins=int(item["wins"]),
            win_rate=float(item["win_rate"]),
            average_rank=float(item["average_rank"]),
        )
        for item in summary["results"]  # type: ignore[index]
    ]
    return BatchSimulationResult(
        rows=rank_simulation_rows(rows, participant_count=max(1, len(rows))),
        seed_mode=resolved_seed.mode,
        seed=resolved_seed.seed,
        completed_runs=int(summary["completed_runs"]),
        total_runs=int(summary["runs"]),
        cancelled=bool(summary["cancelled"]),
    )


def _view_state_from_snapshot(
    snapshot: RaceSnapshot,
    *,
    config: RaceConfig,
    last_move: MoveResult | None,
) -> RaceViewState:
    dango_names = {dango.id: dango.name for dango in config.dangos}
    avatar_labels = {
        dango_id: avatar_label_for_name(name)
        for dango_id, name in dango_names.items()
    }
    ranking_rows = tuple(
        RankingViewRow(
            dango_id=dango_id,
            name=dango_names.get(dango_id, dango_id),
            position=snapshot.positions[dango_id],
            avatar_label=avatar_labels.get(dango_id, avatar_label_for_name(dango_id)),
        )
        for dango_id in snapshot.live_rankings
    )
    return RaceViewState(
        positions=dict(snapshot.positions),
        stacks={position: list(stack) for position, stack in snapshot.stacks.items()},
        devices={position: device.value for position, device in config.track.devices.items()},
        current_actor=last_move.dango_id if last_move else None,
        last_roll=last_move.roll if last_move else None,
        event_log=tuple(event.message for event in snapshot.event_log),
        rankings=tuple(snapshot.rankings),
        live_rankings=tuple(snapshot.live_rankings),
        ranking_rows=ranking_rows,
        dango_names=dango_names,
        avatar_labels=avatar_labels,
        round_number=snapshot.round_number,
        finished=snapshot.finished,
    )
