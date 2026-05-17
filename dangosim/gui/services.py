from __future__ import annotations

from dataclasses import dataclass, replace

from dangosim.cli.main import simulate_many
from dangosim.core.models import MoveResult, RaceConfig, RaceSnapshot
from dangosim.core.simulator import RaceSimulator
from dangosim.gui.view_models import RaceViewState, SimulationResultRow, rank_simulation_rows
from dangosim.randomness import SeedMode, resolve_seed


@dataclass(frozen=True)
class BatchSimulationResult:
    rows: list[SimulationResultRow]
    seed_mode: SeedMode
    seed: int


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
) -> BatchSimulationResult:
    resolved_seed = resolve_seed(mode=seed_mode, requested_seed=seed, config_seed=config.seed)
    summary = simulate_many(
        replace(config, seed=resolved_seed.seed),
        runs=runs,
        seed=resolved_seed.seed,
        seed_mode=resolved_seed.mode,
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
    )


def _view_state_from_snapshot(
    snapshot: RaceSnapshot,
    *,
    config: RaceConfig,
    last_move: MoveResult | None,
) -> RaceViewState:
    return RaceViewState(
        positions=dict(snapshot.positions),
        stacks={position: list(stack) for position, stack in snapshot.stacks.items()},
        devices={position: device.value for position, device in config.track.devices.items()},
        current_actor=last_move.dango_id if last_move else None,
        last_roll=last_move.roll if last_move else None,
        event_log=tuple(event.message for event in snapshot.event_log),
        rankings=tuple(snapshot.rankings),
        finished=snapshot.finished,
    )
