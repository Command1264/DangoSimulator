from __future__ import annotations

from dangosim.core.config_loader import load_race_config
from dangosim.gui.services import GuiRaceController, run_batch_simulation
from dangosim.gui.view_models import build_participant_cards, build_race_config_from_cards
from dangosim.randomness import SeedMode


def _selected_config():
    with open("data/default_race.json", "r", encoding="utf-8") as handle:
        config = load_race_config(handle.read())
    cards = build_participant_cards(config)
    return build_race_config_from_cards(config, cards)


def test_gui_race_controller_exposes_initial_and_step_view_state() -> None:
    controller = GuiRaceController(_selected_config())

    initial = controller.view_state()
    after_step = controller.step()

    assert initial.finished is False
    assert after_step.current_actor is not None
    assert after_step.last_roll is not None
    assert after_step.positions != initial.positions
    assert set(after_step.devices.values())


def test_gui_race_controller_reset_returns_to_initial_positions() -> None:
    controller = GuiRaceController(_selected_config())
    initial = controller.view_state()

    controller.step()
    reset = controller.reset()

    assert reset.positions == initial.positions
    assert reset.event_log == ()


def test_run_batch_simulation_returns_ranked_rows() -> None:
    result = run_batch_simulation(_selected_config(), runs=10, seed=99)

    assert result.seed_mode == SeedMode.FIXED
    assert result.seed == 99
    assert len(result.rows) == 6
    assert result.rows[0].rank == 1
    assert result.rows[0].weighted_score >= result.rows[-1].weighted_score
    assert sum(row.wins for row in result.rows) == 10


def test_run_batch_simulation_can_resolve_system_seed() -> None:
    result = run_batch_simulation(_selected_config(), runs=1, seed=None, seed_mode=SeedMode.SYSTEM)

    assert result.seed_mode == SeedMode.SYSTEM
    assert isinstance(result.seed, int)
