from __future__ import annotations

import json

import pytest

from dangosim.core.config_loader import ConfigValidationError, load_race_config
from dangosim.core.models import AbilityAction, AbilityConfig, DangoConfig, RaceConfig, TrackConfig
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


def test_aemiss_does_not_trigger_when_landing_on_configured_midpoint() -> None:
    payload = {
        "track": {
            "length": 10,
            "finish": 10,
            "devices": [{"position": 6, "type": "midpoint"}],
        },
        "dangos": [
            {
                "id": "aemiss",
                "name": "愛彌斯",
                "start_position": 4,
                "abilities": [
                    {
                        "id": "aemiss_ghost",
                        "name": "電子幽靈登場",
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

    assert simulator.snapshot().positions["aemiss"] == 6


def test_aemiss_triggers_after_moving_past_configured_midpoint() -> None:
    payload = {
        "track": {
            "length": 10,
            "finish": 10,
            "devices": [{"position": 6, "type": "midpoint"}],
        },
        "dangos": [
            {
                "id": "aemiss",
                "name": "愛彌斯",
                "start_position": 4,
                "abilities": [
                    {
                        "id": "aemiss_ghost",
                        "name": "電子幽靈登場",
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
    simulator.step_dango("aemiss", 3)

    assert simulator.snapshot().positions["aemiss"] == 8


def test_linne_unable_to_move_does_not_trigger_device_or_change_stack() -> None:
    payload = {
        "track": {"length": 10, "finish": 10, "devices": [{"position": 3, "type": "advance"}]},
        "dangos": [
            {"id": "other", "name": "Other", "start_position": 3},
            {
                "id": "linne",
                "name": "琳奈",
                "start_position": 3,
                "abilities": [{"id": "linne_colorful", "trigger": "before_move", "actions": [{"type": "builtin"}]}],
            },
        ],
        "seed": 2,
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    initial_stack = list(simulator.snapshot().stacks[3])
    result = simulator.step_dango("linne", 2)
    snapshot = simulator.snapshot()

    assert result.to_position == 3
    assert result.device_triggered.value == "blank"
    assert snapshot.positions["linne"] == 3
    assert snapshot.stacks[3] == initial_stack
    assert all(event.event_type != "device" for event in snapshot.event_log)


def test_phoebe_blessing_uses_named_ability_id() -> None:
    payload = {
        "track": {"length": 10, "finish": 10, "devices": []},
        "dangos": [
            {
                "id": "fei",
                "name": "菲比",
                "start_position": 1,
                "abilities": [
                    {
                        "id": "phoebe_blessing",
                        "name": "歲主庇佑",
                        "trigger": "before_move",
                        "probability": 1.0,
                        "actions": [{"type": "builtin"}],
                    }
                ],
            },
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    result = simulator.step_dango("fei", 1)

    assert result.to_position == 3
    assert "ability:phoebe_blessing" in result.reasons


def test_floro_uses_round_start_bottom_state_for_bonus() -> None:
    payload = {
        "track": {"length": 20, "finish": 20, "devices": []},
        "dangos": [
            {"id": "other", "name": "Other", "start_position": 1},
            {
                "id": "floro",
                "name": "弗洛洛",
                "start_position": 1,
                "abilities": [{"id": "floro_bottom_bonus", "trigger": "before_move", "actions": [{"type": "builtin"}]}],
            },
        ],
        "seed": 0,
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    first = simulator.step_next()
    second = simulator.step_next()

    assert first.dango_id == "other"
    assert second.dango_id == "floro"
    assert "ability:floro_bottom_bonus" not in second.reasons
    assert second.to_position == 1 + second.roll


def test_floro_bottom_bonus_requires_an_actual_stack() -> None:
    payload = {
        "track": {"length": 20, "finish": 20, "devices": []},
        "dangos": [
            {
                "id": "floro",
                "name": "弗洛洛",
                "start_position": 1,
                "abilities": [{"id": "floro_bottom_bonus", "trigger": "before_move", "actions": [{"type": "builtin"}]}],
            },
        ],
        "seed": 0,
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    result = simulator.step_next()

    assert "ability:floro_bottom_bonus" not in result.reasons
    assert result.to_position == 1 + result.roll


def test_sigurd_mark_event_log_uses_target_names_not_ids() -> None:
    payload = {
        "track": {"length": 50, "finish": 50, "devices": []},
        "dangos": [
            {"id": "front_a", "name": "前方甲團子", "start_position": 10},
            {"id": "front_b", "name": "前方乙團子", "start_position": 9},
            {
                "id": "sigurd",
                "name": "西格莉卡團子",
                "start_position": 1,
                "abilities": [
                    {"id": "sigurd_sun_help", "name": "太陽援助", "trigger": "after_roll", "actions": [{"type": "builtin"}]}
                ],
            },
            {"id": "behind", "name": "後方團子", "start_position": 1},
        ],
        "seed": 4,
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    for _ in range(5):
        simulator.step_next()

    message = next(event.message for event in simulator.snapshot().event_log if "標記前方團子" in event.message)
    assert "前方甲團子" in message
    assert "前方乙團子" in message
    assert "front_a" not in message
    assert "front_b" not in message


def test_after_roll_sigurd_penalty_applies_before_first_actor_moves_each_round() -> None:
    config = RaceConfig(
        track=TrackConfig(length=50, finish=50),
        dangos=[
            DangoConfig(id="front", name="前方團子", start_position=12),
            DangoConfig(
                id="sigurd",
                name="西格莉卡團子",
                start_position=4,
                abilities=(
                    AbilityConfig(
                        id="sigurd_sun_help",
                        name="日靈，幫幫忙!",
                        trigger="after_roll",
                        actions=(AbilityAction(type="builtin"),),
                    ),
                ),
            ),
            DangoConfig(id="behind", name="後方團子", start_position=1),
        ],
        seed=0,
        first_round_order={"front": 1, "sigurd": 2, "behind": 3},
    )
    simulator = RaceSimulator(config)

    first = simulator.step_next()
    first_round_marks = [event for event in simulator.snapshot().event_log if "標記前方團子" in event.message]
    while simulator.snapshot().round_number == 1:
        simulator.step_next()
    simulator.step_next()
    all_marks = [event for event in simulator.snapshot().event_log if "標記前方團子" in event.message]

    assert first.dango_id == "front"
    assert "round_penalty" in first.reasons
    assert first.to_position == first.from_position + max(1, first.roll - 1)
    assert len(first_round_marks) == 1
    assert len(all_marks) == 2


def test_round_start_ability_triggers_before_action_order_is_announced() -> None:
    payload = {
        "track": {"length": 30, "finish": 30, "devices": []},
        "dangos": [
            {"id": "bottom", "name": "Bottom", "start_position": 1},
            {
                "id": "augusta",
                "name": "奧古斯塔",
                "start_position": 1,
                "abilities": [{"id": "augusta_governor_authority", "name": "總督權柄", "trigger": "round_start", "actions": [{"type": "builtin"}]}],
            },
            {"id": "other", "name": "Other", "start_position": 2},
        ],
        "seed": 0,
    }
    simulator = RaceSimulator(load_race_config(json.dumps(payload)))

    simulator.step_next()
    events = simulator.snapshot().event_log
    ability_index = next(index for index, event in enumerate(events) if event.data.get("ability_id") == "augusta_governor_authority")
    order_index = next(index for index, event in enumerate(events) if event.event_type == "round_start")

    assert ability_index < order_index


def test_load_race_config_accepts_after_roll_ability_trigger() -> None:
    payload = {
        "track": {"length": 8, "finish": 8, "devices": []},
        "dangos": [
            {
                "id": "sigurd",
                "name": "西格莉卡團子",
                "start_position": 1,
                "abilities": [{"id": "sigurd_sun_help", "name": "日靈，幫幫忙!", "trigger": "after_roll", "actions": [{"type": "builtin"}]}],
            }
        ],
    }

    config = load_race_config(json.dumps(payload))

    assert config.dangos[0].abilities[0].trigger == "after_roll"


def test_load_race_config_accepts_round_end_ability_trigger() -> None:
    payload = {
        "track": {"length": 8, "finish": 8, "devices": []},
        "dangos": [
            {
                "id": "changli",
                "name": "長離團子",
                "start_position": 1,
                "abilities": [{"id": "changli_strategic_delay", "name": "謀而後定", "trigger": "round_end", "actions": [{"type": "builtin"}]}],
            }
        ],
    }

    config = load_race_config(json.dumps(payload))

    assert config.dangos[0].abilities[0].trigger == "round_end"


def test_chisaki_gains_bonus_when_roll_is_round_minimum() -> None:
    payload = {
        "track": {"length": 20, "finish": 20, "devices": []},
        "dangos": [
            {
                "id": "chisaki",
                "name": "千咲",
                "start_position": 1,
                "abilities": [{"id": "chisaki_threshold_analysis", "name": "視閾解明", "trigger": "before_move", "actions": [{"type": "builtin"}]}],
            },
            {"id": "other", "name": "Other", "start_position": 1},
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    simulator._round_rolls = {"chisaki": 1, "other": 3}
    result = simulator.step_dango("chisaki", 1)

    assert "ability:chisaki_threshold_analysis" in result.reasons
    assert result.to_position == 4


def test_chisaki_compares_against_full_round_roll_snapshot_after_others_act() -> None:
    payload = {
        "track": {"length": 20, "finish": 20, "devices": []},
        "dangos": [
            {"id": "other", "name": "Other", "start_position": 1},
            {
                "id": "chisaki",
                "name": "千咲",
                "start_position": 1,
                "abilities": [{"id": "chisaki_threshold_analysis", "name": "視閾解明", "trigger": "before_move", "actions": [{"type": "builtin"}]}],
            },
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    simulator._turn_queue = ["other", "chisaki"]
    simulator._round_number = 1
    simulator._round_rolls = {"other": 1, "chisaki": 2}

    simulator.step_next()
    result = simulator.step_next()

    assert "ability:chisaki_threshold_analysis" not in result.reasons
    assert result.to_position == 3


def test_chisaki_does_not_trigger_without_round_roll_snapshot() -> None:
    payload = {
        "track": {"length": 20, "finish": 20, "devices": []},
        "dangos": [
            {
                "id": "chisaki",
                "name": "千咲",
                "start_position": 1,
                "abilities": [{"id": "chisaki_threshold_analysis", "name": "視閾解明", "trigger": "before_move", "actions": [{"type": "builtin"}]}],
            },
            {"id": "other", "name": "Other", "start_position": 1},
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    result = simulator.step_dango("chisaki", 3)

    assert "ability:chisaki_threshold_analysis" not in result.reasons
    assert result.to_position == 4


def test_moning_rolls_three_two_one_cycle() -> None:
    payload = {
        "track": {"length": 20, "finish": 20, "devices": []},
        "dangos": [
            {
                "id": "moning",
                "name": "莫寧",
                "start_position": 1,
                "abilities": [{"id": "moning_precision_calculation", "name": "精密演算", "trigger": "before_move", "actions": [{"type": "builtin"}]}],
            }
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    rolls = [simulator.step_next().roll for _ in range(4)]

    assert rolls == [3, 2, 1, 3]


def test_augusta_skips_current_turn_and_moves_last_next_round_when_top_of_stack() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=30, finish=30),
            dangos=[
                DangoConfig(id="boss", name="布大王", start_position=1, is_boss=True, ranked=False),
                DangoConfig(
                    id="augusta",
                    name="奧古斯塔",
                    start_position=1,
                    abilities=(
                        AbilityConfig(
                            id="augusta_governor_authority",
                            name="總督權柄",
                            trigger="round_start",
                            actions=(AbilityAction(type="builtin"),),
                        ),
                    ),
                ),
                DangoConfig(id="other", name="Other", start_position=2),
            ],
            seed=0,
            first_round_order={"augusta": 1, "other": 2},
        )
    )
    first_round_results = [simulator.step_next() for _ in range(2)]
    augusta_result = next(result for result in first_round_results if result.dango_id == "augusta")

    assert augusta_result.to_position == 1
    assert "ability:augusta_governor_authority" in augusta_result.reasons

    second_round_results = []
    while True:
        result = simulator.step_next()
        second_round_results.append(result)
        if result.dango_id == "augusta":
            break
    round_events = [event for event in simulator.snapshot().event_log if event.event_type == "round_start"]

    assert round_events[-1].data["order"][-1] == "augusta"
    assert second_round_results[-1].dango_id == "augusta"
    assert second_round_results[-1].to_position != second_round_results[-1].from_position
    assert "ability:augusta_governor_authority" not in second_round_results[-1].reasons


def test_yuno_pulls_all_regulars_to_self_in_rank_order_after_midpoint_when_middle_rank() -> None:
    payload = {
        "track": {"length": 20, "finish": 20, "devices": [{"position": 10, "type": "midpoint"}]},
        "dangos": [
            {"id": "leader", "name": "Leader", "start_position": 16},
            {
                "id": "yuno",
                "name": "尤諾",
                "start_position": 9,
                "abilities": [{"id": "yuno_anchor_fate", "name": "錨定命途", "trigger": "after_move", "once_per_race": True, "actions": [{"type": "builtin"}]}],
            },
            {"id": "behind", "name": "Behind", "start_position": 5},
            {"id": "tail", "name": "Tail", "start_position": 2},
            {"id": "boss", "name": "布大王", "start_position": 20, "is_boss": True, "ranked": False},
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    simulator.step_dango("yuno", 2)
    snapshot = simulator.snapshot()

    assert snapshot.positions["leader"] == 11
    assert snapshot.positions["yuno"] == 11
    assert snapshot.positions["behind"] == 11
    assert snapshot.positions["tail"] == 11
    assert snapshot.positions["boss"] == 20
    assert snapshot.stacks[11] == ["tail", "behind", "yuno", "leader"]


def test_aemiss_unlocks_after_midpoint_and_uses_once_when_target_later_exists() -> None:
    payload = {
        "track": {"length": 20, "finish": 20, "devices": [{"position": 10, "type": "midpoint"}]},
        "dangos": [
            {
                "id": "aemiss",
                "name": "愛彌斯",
                "start_position": 9,
                "abilities": [
                    {
                        "id": "aemiss_ghost",
                        "name": "電子幽靈登場",
                        "trigger": "after_move",
                        "once_per_race": True,
                        "actions": [{"type": "builtin"}],
                    }
                ],
            },
            {"id": "target", "name": "Target", "start_position": 5},
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    simulator.step_dango("aemiss", 2)
    simulator.step_dango("target", 8)
    simulator.step_dango("aemiss", 1)
    snapshot = simulator.snapshot()
    ability_events = [event for event in snapshot.event_log if event.data.get("ability_id") == "aemiss_ghost"]

    assert snapshot.positions["aemiss"] == 13
    assert snapshot.positions["target"] == 13
    assert snapshot.stacks[13] == ["target", "aemiss"]
    assert len(ability_events) == 1


def test_changli_round_end_sets_next_round_last_when_stacked_above_another_dango() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=30, finish=30),
            dangos=[
                DangoConfig(id="bottom", name="Bottom", start_position=4),
                DangoConfig(
                    id="changli",
                    name="長離",
                    start_position=1,
                    abilities=(
                        AbilityConfig(
                            id="changli_strategic_delay",
                            name="謀而後定",
                            trigger="round_end",
                            probability=1.0,
                            actions=(AbilityAction(type="builtin"),),
                        ),
                    ),
                ),
            ],
            seed=0,
        )
    )
    simulator._turn_queue = ["changli"]
    simulator._round_order = ["changli"]
    simulator._round_number = 1
    simulator._round_rolls = {"changli": 3}

    simulator.step_next()
    assert simulator.snapshot().stacks[4] == ["bottom", "changli"]
    ability_events = [
        event
        for event in simulator.snapshot().event_log
        if event.data.get("ability_id") == "changli_strategic_delay"
    ]
    assert len(ability_events) == 1

    simulator.step_next()
    round_events = [event for event in simulator.snapshot().event_log if event.event_type == "round_start"]

    assert round_events[-1].data["order"][-1] == "changli"


def test_jinhsi_moves_to_stack_top_at_round_end() -> None:
    simulator = RaceSimulator(
        RaceConfig(
            track=TrackConfig(length=20, finish=20),
            dangos=[
                DangoConfig(
                    id="jinhsi",
                    name="今汐",
                    start_position=3,
                    abilities=(
                        AbilityConfig(
                            id="jinhsi_magistrate_name",
                            name="令尹之名",
                            trigger="round_end",
                            probability=1.0,
                            actions=(AbilityAction(type="builtin"),),
                        ),
                    ),
                ),
                DangoConfig(id="top", name="Top", start_position=1),
            ],
        )
    )
    simulator._turn_queue = ["jinhsi", "top"]
    simulator._round_order = ["jinhsi", "top"]
    simulator._round_number = 1
    simulator._round_rolls = {"jinhsi": 1, "top": 3}

    result = simulator.step_next()
    assert result.carried == ("jinhsi",)
    assert simulator.snapshot().stacks[4] == ["jinhsi"]

    simulator.step_next()
    snapshot = simulator.snapshot()

    assert snapshot.positions["jinhsi"] == 4
    assert snapshot.positions["top"] == 4
    assert snapshot.stacks[4] == ["top", "jinhsi"]


def test_calcharo_gains_bonus_when_starting_move_in_last_place() -> None:
    payload = {
        "track": {"length": 20, "finish": 20, "devices": []},
        "dangos": [
            {"id": "ahead", "name": "Ahead", "start_position": 5},
            {
                "id": "calcharo",
                "name": "卡卡羅",
                "start_position": 1,
                "abilities": [{"id": "calcharo_shadow_follow", "name": "如影隨形", "trigger": "before_move", "actions": [{"type": "builtin"}]}],
            },
        ],
    }

    simulator = RaceSimulator(load_race_config(json.dumps(payload)))
    result = simulator.step_dango("calcharo", 1)

    assert "ability:calcharo_shadow_follow" in result.reasons
    assert result.to_position == 5
