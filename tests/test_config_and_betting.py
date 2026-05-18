from __future__ import annotations

import json

import pytest

from dangosim.core.betting import BettingFormula, BetLedger
from dangosim.core.config_loader import ConfigValidationError, load_race_config
from dangosim.core.models import DeviceType


def test_load_race_config_rejects_unknown_device_type() -> None:
    payload = {
        "track": {"length": 8, "finish": 8, "devices": [{"position": 2, "type": "trap"}]},
        "dangos": [{"id": "a", "name": "A", "start_position": 1}],
    }

    with pytest.raises(ConfigValidationError, match="Unknown device type"):
        load_race_config(json.dumps(payload))


def test_load_race_config_parses_devices_and_boss_mode() -> None:
    payload = {
        "track": {"length": 8, "finish": 8, "devices": [{"position": 3, "type": "advance"}]},
        "dangos": [
            {"id": "a", "name": "A", "start_position": 1},
            {"id": "boss", "name": "布大王", "start_position": 8, "is_boss": True},
        ],
        "boss_ranked": True,
        "seed": 11,
    }

    config = load_race_config(json.dumps(payload))

    assert config.track.devices[3] == DeviceType.ADVANCE
    assert config.boss_ranked is True
    assert config.seed == 11


def test_load_race_config_parses_ability_display_name() -> None:
    payload = {
        "track": {"length": 8, "finish": 8, "devices": []},
        "dangos": [
            {
                "id": "a",
                "name": "A",
                "start_position": 1,
                "abilities": [
                    {
                        "id": "sample_ability",
                        "name": "顯示技能",
                        "trigger": "before_move",
                        "actions": [{"type": "builtin"}],
                    }
                ],
            }
        ],
    }

    config = load_race_config(json.dumps(payload))

    assert config.dangos[0].abilities[0].id == "sample_ability"
    assert config.dangos[0].abilities[0].name == "顯示技能"


def test_betting_ledger_settles_with_configurable_formula() -> None:
    formula = BettingFormula(wrong_refund_rate=0.8, rank_rewards={1: 1.0, 2: 0.4})
    ledger = BetLedger(initial_popularity=1000, formula=formula)

    ledger.place_bet(race_id="r1", dango_id="a", amount=100, dark_horse_value=2.5)
    ledger.place_bet(race_id="r1", dango_id="b", amount=200, dark_horse_value=1.2)
    result = ledger.settle(race_id="r1", rankings=["a", "b"])

    assert result.balance == 1000 - 300 + 250 + 96
    assert result.entries["a"].reward == 250
    assert result.entries["b"].reward == 96
