from __future__ import annotations

from dataclasses import replace

from dangosim.cli.main import simulate_many
from dangosim.core.models import MoveResult, RaceConfig, RaceSnapshot
from dangosim.core.simulator import RaceSimulator
from dangosim.gui.view_models import RaceViewState, SimulationResultRow, rank_simulation_rows


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


def run_batch_simulation(config: RaceConfig, *, runs: int, seed: int | None) -> list[SimulationResultRow]:
    summary = simulate_many(replace(config, seed=seed), runs=runs, seed=seed)
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
    return rank_simulation_rows(rows, participant_count=max(1, len(rows)))


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
