from __future__ import annotations

from dangosim.core.config_loader import load_race_config
from dangosim.gui.view_models import (
    BossMode,
    ParticipantCardState,
    SimulationResultRow,
    avatar_label_for_name,
    build_participant_cards,
    build_race_config_from_cards,
    format_event_log_message,
    is_auto_play_control_enabled,
    rank_simulation_rows,
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
    assert all(card.group == "" for card in cards)
    assert boss.name == "布大王"
    assert boss.selected is True
    assert boss.boss_mode == BossMode.DISRUPTOR
    assert all(card.skill_note for card in cards)


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
    assert format_event_log_message("第 1 回合行動順序：lu、fei") == "第 1 回合行動順序：lu、fei"
    assert format_event_log_message("比賽結束，菲比團子 取得第 1 名。") == "比賽結束，菲比團子 取得第 1 名。"
    assert format_event_log_message("菲比團子 觸發 advance") == "　　菲比團子 觸發 advance"


def test_auto_play_control_is_available_before_and_after_single_race_start() -> None:
    assert is_auto_play_control_enabled(single_race_active=False, batch_running=False) is True
    assert is_auto_play_control_enabled(single_race_active=True, batch_running=False) is True
    assert is_auto_play_control_enabled(single_race_active=False, batch_running=True) is False


def test_participant_card_state_rejects_ranked_boss_mode_for_non_boss() -> None:
    card = ParticipantCardState(
        dango_id="lu",
        name="陸・赫斯團子",
        group="A組",
        skill_note="測試",
        selected=True,
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
