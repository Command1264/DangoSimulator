from __future__ import annotations

from pathlib import Path

import pytest

from dangosim.core.config_loader import load_race_config
from dangosim.gui.settings import (
    BatchSimulationSettings,
    ParticipantOverrideSettings,
    ParticipantSettings,
    SingleRaceSettings,
    UserSettings,
    UserSettingsStore,
    apply_settings_to_cards,
)
from dangosim.gui.view_models import BossMode, build_participant_cards


def _default_cards():
    config = load_race_config(Path("data/default_race.json").read_text(encoding="utf-8"))
    return build_participant_cards(config)


def test_user_settings_round_trip_json(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    store = UserSettingsStore(settings_path)
    settings = UserSettings(
        participants=ParticipantSettings(
            selected_dango_ids=("lu", "fei"),
            boss_mode=BossMode.RANKED.value,
            participant_overrides=(
                ParticipantOverrideSettings(
                    dango_id="lu",
                    selected=True,
                    start_position=4,
                    initial_stack_order=2,
                    first_round_order=1,
                ),
            ),
        ),
        single_race=SingleRaceSettings(speed_ms=450, auto_play=True),
        batch_simulation=BatchSimulationSettings(
            runs=2500,
            seed_mode="system",
            seed="123456",
            sort_mode="勝率",
            workers="4",
        ),
    )

    store.save(settings)

    assert store.load() == settings


def test_user_settings_loads_defaults_for_missing_or_invalid_file(tmp_path: Path) -> None:
    missing_store = UserSettingsStore(tmp_path / "missing.json")
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{bad json", encoding="utf-8")

    assert missing_store.load() == UserSettings()
    assert UserSettingsStore(invalid_path).load() == UserSettings()


def test_user_settings_validates_bounds_and_enums(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dangosim.gui.settings.os.cpu_count", lambda: 4)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        """
        {
          "version": 1,
          "participants": {
            "selected_dango_ids": ["lu", 123, "unknown"],
            "boss_mode": "bad",
            "participant_overrides": [
              {
                "dango_id": "lu",
                "selected": true,
                "start_position": 999,
                "initial_stack_order": 2,
                "first_round_order": 1
              },
              {
                "dango_id": "",
                "selected": true,
                "start_position": -1,
                "initial_stack_order": 0,
                "first_round_order": "bad"
              }
            ]
          },
          "single_race": { "speed_ms": 1, "auto_play": "bad" },
          "batch_simulation": {
            "runs": 999999999,
            "seed_mode": "bad",
            "seed": 123,
            "sort_mode": "bad",
            "workers": "8"
          }
        }
        """,
        encoding="utf-8",
    )

    settings = UserSettingsStore(settings_path).load()

    assert settings.participants.selected_dango_ids == ("lu", "unknown")
    assert settings.participants.boss_mode == BossMode.DISRUPTOR.value
    assert settings.participants.participant_overrides == (
        ParticipantOverrideSettings(
            dango_id="lu",
            selected=True,
            start_position=999,
            initial_stack_order=2,
            first_round_order=1,
        ),
    )
    assert settings.single_race.speed_ms == 150
    assert settings.single_race.auto_play is False
    assert settings.batch_simulation.runs == 99_999_999
    assert settings.batch_simulation.seed_mode == "fixed"
    assert settings.batch_simulation.seed == "123"
    assert settings.batch_simulation.sort_mode == "綜合分數"
    assert settings.batch_simulation.workers == "auto"


def test_user_settings_accepts_full_worker_mode(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        """
        {
          "version": 1,
          "batch_simulation": { "workers": "full" }
        }
        """,
        encoding="utf-8",
    )

    settings = UserSettingsStore(settings_path).load()

    assert settings.batch_simulation.workers == "full"


def test_apply_settings_to_cards_restores_participants_and_boss_mode() -> None:
    cards = apply_settings_to_cards(
        _default_cards(),
        UserSettings(
            participants=ParticipantSettings(
                selected_dango_ids=("lu", "fei"),
                boss_mode=BossMode.RANKED.value,
                participant_overrides=(
                    ParticipantOverrideSettings(
                        dango_id="lu",
                        selected=True,
                        start_position=5,
                        initial_stack_order=2,
                        first_round_order=1,
                    ),
                    ParticipantOverrideSettings(
                        dango_id="fei",
                        selected=True,
                        start_position=6,
                        initial_stack_order=None,
                        first_round_order=None,
                    ),
                ),
            )
        ),
    )

    selected = {card.dango_id for card in cards if card.selected and not card.is_boss}
    boss = next(card for card in cards if card.is_boss)

    assert selected == {"lu", "fei"}
    assert boss.boss_mode == BossMode.RANKED
    lu = next(card for card in cards if card.dango_id == "lu")
    fei = next(card for card in cards if card.dango_id == "fei")
    assert lu.start_position == 5
    assert lu.initial_stack_order == 2
    assert lu.first_round_order == 1
    assert fei.start_position == 6


def test_apply_settings_to_cards_ignores_out_of_range_start_position() -> None:
    cards = apply_settings_to_cards(
        _default_cards(),
        UserSettings(
            participants=ParticipantSettings(
                selected_dango_ids=("lu",),
                participant_overrides=(
                    ParticipantOverrideSettings(
                        dango_id="lu",
                        selected=True,
                        start_position=999,
                    ),
                ),
            )
        ),
    )

    lu = next(card for card in cards if card.dango_id == "lu")
    assert lu.start_position == 1
