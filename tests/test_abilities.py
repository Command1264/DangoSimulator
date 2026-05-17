from __future__ import annotations

import json

import pytest

from dangosim.core.config_loader import ConfigValidationError, load_race_config
from dangosim.core.simulator import RaceSimulator


def test_before_move_add_steps_ability_extends_roll() -> None:
    payload = {
        "track": {"length": 8, "finish": 8, "devices": []},
        "dangos": [
            {
                "id": "fast",
                "name": "Fast",
                "start_position": 1,
                "abilities": [
                    {
                        "id": "bonus",
                        "trigger": "before_move",
                        "conditions": [{"type": "always"}],
                        "actions": [{"type": "add_steps", "value": 1}],
                    }
                ],
            }
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    result = simulator.step_dango("fast", 1)

    assert result.to_position == 3
    assert result.reasons == ("ability:bonus",)


def test_load_race_config_rejects_unknown_ability_action() -> None:
    payload = {
        "track": {"length": 8, "finish": 8, "devices": []},
        "dangos": [
            {
                "id": "unsafe",
                "name": "Unsafe",
                "start_position": 1,
                "abilities": [
                    {
                        "id": "unsafe_action",
                        "trigger": "before_move",
                        "actions": [{"type": "exec", "value": "print('no')"}],
                    }
                ],
            }
        ],
    }

    with pytest.raises(ConfigValidationError, match="Unknown ability action"):
        load_race_config(json.dumps(payload))


def test_lu_device_ability_modifies_advance_and_block_devices() -> None:
    payload = {
        "track": {
            "length": 12,
            "finish": 12,
            "devices": [{"position": 3, "type": "advance"}, {"position": 7, "type": "block"}],
        },
        "dangos": [
            {
                "id": "lu",
                "name": "陸赫斯",
                "start_position": 1,
                "abilities": [
                    {"id": "lu_device_master", "trigger": "on_device", "actions": [{"type": "builtin"}]}
                ],
            },
            {
                "id": "lu_block",
                "name": "陸赫斯2",
                "start_position": 5,
                "abilities": [
                    {"id": "lu_device_master", "trigger": "on_device", "actions": [{"type": "builtin"}]}
                ],
            },
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))

    assert simulator.step_dango("lu", 2).to_position == 7
    assert simulator.step_dango("lu_block", 2).to_position == 5


def test_daphne_same_roll_ability_uses_previous_roll() -> None:
    payload = {
        "track": {"length": 12, "finish": 12, "devices": []},
        "dangos": [
            {
                "id": "daphne",
                "name": "達妮婭",
                "start_position": 1,
                "abilities": [
                    {"id": "daphne_same_roll_bonus", "trigger": "before_move", "actions": [{"type": "builtin"}]}
                ],
            }
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))

    assert simulator.step_dango("daphne", 2).to_position == 3
    assert simulator.step_dango("daphne", 2).to_position == 7


def test_snow_gains_bonus_after_meeting_boss() -> None:
    payload = {
        "track": {"length": 12, "finish": 12, "devices": []},
        "dangos": [
            {
                "id": "snow",
                "name": "緋雪",
                "start_position": 5,
                "abilities": [{"id": "snow_bird", "trigger": "before_move", "actions": [{"type": "builtin"}]}],
            },
            {"id": "boss", "name": "布大王", "start_position": 10, "is_boss": True, "ranked": False},
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))

    simulator.step_dango("boss", 5)
    assert simulator.step_dango("snow", 1).to_position == 7


def test_shorekeeper_rolls_only_two_or_three() -> None:
    payload = {
        "track": {"length": 30, "finish": 30, "devices": []},
        "dangos": [
            {
                "id": "shorekeeper",
                "name": "守岸人",
                "start_position": 1,
                "abilities": [
                    {"id": "shorekeeper_future", "trigger": "before_move", "actions": [{"type": "builtin"}]}
                ],
            }
        ],
        "seed": 5,
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    rolls = [simulator.step_next().roll for _ in range(5)]

    assert set(rolls).issubset({2, 3})


def test_aemiss_teleports_to_nearest_regular_ahead_after_crossing_midpoint() -> None:
    payload = {
        "track": {"length": 10, "finish": 10, "devices": []},
        "dangos": [
            {
                "id": "aemiss",
                "name": "愛彌斯",
                "start_position": 4,
                "abilities": [
                    {
                        "id": "aemiss_ghost",
                        "trigger": "after_move",
                        "once_per_race": True,
                        "actions": [{"type": "builtin"}],
                    }
                ],
            },
            {"id": "target", "name": "Target", "start_position": 8},
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    simulator.step_dango("aemiss", 2)

    snapshot = simulator.snapshot()
    assert snapshot.positions["aemiss"] == 8
    assert snapshot.stacks[8] == ["target", "aemiss"]
