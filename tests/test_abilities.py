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
