from __future__ import annotations

from dangosim.core.config_loader import load_race_config
from dangosim.core.models import DangoConfig, RaceConfig, TrackConfig
from dangosim.gui.view_models import (
    BossMode,
    ParticipantCardState,
    SimulationResultRow,
    avatar_label_for_name,
    build_participant_cards,
    build_race_config_from_cards,
    dango_display_name,
    device_display_name,
    format_event_log_message,
    is_auto_play_control_enabled,
    is_seed_input_enabled,
    participant_selection_summary,
    rank_simulation_rows,
    track_cell_tooltip,
)
import pytest


def _default_config():
    with open("data/default_race.json", "r", encoding="utf-8") as handle:
        return load_race_config(handle.read())


def test_build_participant_cards_selects_general_dangos_and_marks_boss_as_disruptor() -> None:
    cards = build_participant_cards(_default_config())

    selected = [card for card in cards if card.selected and not card.is_boss]
    boss = next(card for card in cards if card.is_boss)

    assert len(selected) == 6
    assert any(card.dango_id == "shorekeeper" and not card.selected for card in cards)
    assert any(card.group for card in cards)
    assert boss.name == "布大王"
    assert boss.selected is True
    assert boss.boss_mode == BossMode.DISRUPTOR
    assert all(card.skill_note for card in cards)
    assert all(card.start_position >= 1 for card in cards)


def test_build_race_config_from_cards_uses_selected_general_dangos_and_boss_mode() -> None:
    config = _default_config()
    cards = build_participant_cards(config)
    limited_cards = []
    for card in cards:
        if card.is_boss:
            limited_cards.append(card.with_updates(selected=True, boss_mode=BossMode.RANKED))
        else:
            limited_cards.append(card.with_updates(selected=card.dango_id in {"lu", "fei"}))

    race_config = build_race_config_from_cards(config, limited_cards)

    assert [dango.id for dango in race_config.dangos] == ["lu", "fei", "boss"]
    assert race_config.boss_ranked is True
    assert next(dango for dango in race_config.dangos if dango.id == "boss").ranked is True


def test_build_race_config_from_cards_applies_start_and_order_overrides() -> None:
    config = _default_config()
    cards = []
    for card in build_participant_cards(config):
        if card.dango_id == "lu":
            cards.append(
                card.with_updates(
                    selected=True,
                    start_position=4,
                    initial_stack_order=2,
                    first_round_order=1,
                )
            )
        elif card.dango_id == "fei":
            cards.append(
                card.with_updates(
                    selected=True,
                    start_position=4,
                    initial_stack_order=1,
                    first_round_order=2,
                )
            )
        elif card.is_boss:
            cards.append(card.with_updates(selected=True, boss_mode=BossMode.DISRUPTOR))
        else:
            cards.append(card.with_updates(selected=False))

    race_config = build_race_config_from_cards(config, cards)

    assert {dango.id: dango.start_position for dango in race_config.dangos}["lu"] == 4
    assert {dango.id: dango.start_position for dango in race_config.dangos}["fei"] == 4
    assert race_config.initial_stack_order == {"lu": 2, "fei": 1}
    assert race_config.first_round_order == {"lu": 1, "fei": 2}


def test_build_race_config_from_cards_does_not_limit_selected_dango_count() -> None:
    config = _default_config()
    general_ids = [dango.id for dango in config.dangos if not dango.is_boss][:7]
    cards = [
        card.with_updates(selected=card.dango_id in general_ids)
        if not card.is_boss
        else card.with_updates(selected=True, boss_mode=BossMode.DISRUPTOR)
        for card in build_participant_cards(config)
    ]

    race_config = build_race_config_from_cards(config, cards)

    assert [dango.id for dango in race_config.dangos if not dango.is_boss] == general_ids


def test_build_participant_cards_hides_wip_group_labels() -> None:
    cards = build_participant_cards(
        RaceConfig(
            track=TrackConfig(length=8, finish=8),
            dangos=[DangoConfig(id="draft", name="Draft", start_position=1, group="WIP")],
        )
    )

    assert cards[0].group == ""


def test_rank_simulation_rows_uses_70_30_weighted_score() -> None:
    rows = [
        SimulationResultRow("fast", "Fast", wins=60, win_rate=0.60, average_rank=2.8),
        SimulationResultRow("stable", "Stable", wins=50, win_rate=0.50, average_rank=1.8),
    ]

    ranked = rank_simulation_rows(rows, participant_count=6)

    assert ranked[0].dango_id == "fast"
    assert ranked[0].rank == 1
    assert ranked[0].weighted_score > ranked[1].weighted_score


def test_avatar_label_uses_first_visible_name_character() -> None:
    assert avatar_label_for_name("布大王") == "布"
    assert avatar_label_for_name("  菲比團子") == "菲"


def test_format_event_log_message_only_indents_detail_events() -> None:
    assert format_event_log_message("第 1 回合行動順序：陸赫斯團子、菲比團子") == "第 1 回合行動順序：陸赫斯團子、菲比團子"
    assert format_event_log_message("比賽結束，菲比團子 取得第 1 名。") == "比賽結束，菲比團子 取得第 1 名。"
    assert format_event_log_message("菲比團子 觸發 推進裝置") == "　　菲比團子 觸發 推進裝置"


def test_track_cell_tooltip_uses_device_display_names_not_ids() -> None:
    assert device_display_name("advance") == "推進裝置"
    assert device_display_name("block") == "阻遏裝置"
    assert device_display_name("time_rift") == "時空裂隙"
    assert track_cell_tooltip(index=3, device="advance", is_midpoint=False) == "格 3 推進裝置"
    assert track_cell_tooltip(index=15, device="block", is_midpoint=True) == "格 15 阻遏裝置 / 中點"


def test_visible_dango_name_fallback_does_not_expose_id() -> None:
    assert dango_display_name("lu", {"lu": "陸赫斯團子"}) == "陸赫斯團子"
    assert dango_display_name("unknown_id", {}) == "未知團子"
    assert dango_display_name(None, {}) == "-"


def test_participant_selection_summary_has_no_upper_limit_text() -> None:
    cards = [
        ParticipantCardState("a", "A", "二週年", "A skill", True, start_position=1),
        ParticipantCardState("b", "B", "二週年", "B skill", True, start_position=1),
        ParticipantCardState("c", "C", "二週年", "C skill", True, start_position=1),
        ParticipantCardState("d", "D", "二週年", "D skill", True, start_position=1),
        ParticipantCardState("e", "E", "二週年", "E skill", True, start_position=1),
        ParticipantCardState("f", "F", "二週年", "F skill", True, start_position=1),
        ParticipantCardState("g", "G", "二週年", "G skill", True, start_position=1),
    ]

    assert participant_selection_summary(cards).startswith("已選 7 顆")
    assert "/6" not in participant_selection_summary(cards)


def test_auto_play_control_is_available_before_and_after_single_race_start() -> None:
    assert is_auto_play_control_enabled(single_race_active=False, batch_running=False) is True
    assert is_auto_play_control_enabled(single_race_active=True, batch_running=False) is True
    assert is_auto_play_control_enabled(single_race_active=False, batch_running=True) is False


def test_seed_input_is_enabled_only_for_fixed_seed_when_controls_are_available() -> None:
    assert is_seed_input_enabled(seed_mode="fixed", batch_controls_enabled=True) is True
    assert is_seed_input_enabled(seed_mode="system", batch_controls_enabled=True) is False
    assert is_seed_input_enabled(seed_mode="fixed", batch_controls_enabled=False) is False


def test_participant_card_state_rejects_ranked_boss_mode_for_non_boss() -> None:
    card = ParticipantCardState(
        dango_id="lu",
        name="陸・赫斯團子",
        group="A組",
        skill_note="測試",
        selected=True,
        start_position=1,
        is_boss=False,
        boss_mode=BossMode.RANKED,
    )

    normalized = card.normalized()

    assert normalized.boss_mode == BossMode.NONE


def test_build_race_config_from_cards_requires_at_least_one_ranked_general_dango() -> None:
    config = _default_config()
    cards = [
        card.with_updates(selected=False)
        if not card.is_boss
        else card.with_updates(selected=True, boss_mode=BossMode.DISRUPTOR)
        for card in build_participant_cards(config)
    ]

    with pytest.raises(ValueError, match="至少選擇 1 顆一般團子"):
        build_race_config_from_cards(config, cards)
