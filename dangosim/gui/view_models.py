from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum

from dangosim.core.models import DangoConfig, RaceConfig

DEVICE_DISPLAY_NAMES = {
    "": "空白",
    "blank": "空白",
    "advance": "推進裝置",
    "block": "阻遏裝置",
    "time_rift": "時空裂隙",
}


class BossMode(str, Enum):
    NONE = "none"
    DISRUPTOR = "disruptor"
    RANKED = "ranked"


@dataclass(frozen=True)
class ParticipantCardState:
    dango_id: str
    name: str
    group: str
    skill_note: str
    selected: bool
    start_position: int
    initial_stack_order: int | None = None
    first_round_order: int | None = None
    is_boss: bool = False
    boss_mode: BossMode = BossMode.NONE

    def normalized(self) -> "ParticipantCardState":
        if self.is_boss:
            mode = self.boss_mode if self.boss_mode is not BossMode.NONE else BossMode.DISRUPTOR
            return replace(self, selected=True, boss_mode=mode)
        return replace(self, boss_mode=BossMode.NONE)

    def with_updates(
        self,
        *,
        selected: bool | None = None,
        boss_mode: BossMode | None = None,
        start_position: int | None = None,
        initial_stack_order: int | None = None,
        first_round_order: int | None = None,
    ) -> "ParticipantCardState":
        return replace(
            self,
            selected=self.selected if selected is None else selected,
            boss_mode=self.boss_mode if boss_mode is None else boss_mode,
            start_position=self.start_position if start_position is None else start_position,
            initial_stack_order=initial_stack_order if initial_stack_order is not None else self.initial_stack_order,
            first_round_order=first_round_order if first_round_order is not None else self.first_round_order,
        ).normalized()

    def with_order_updates(
        self,
        *,
        initial_stack_order: int | None,
        first_round_order: int | None,
    ) -> "ParticipantCardState":
        return replace(
            self,
            initial_stack_order=initial_stack_order,
            first_round_order=first_round_order,
        ).normalized()


@dataclass(frozen=True)
class RankingViewRow:
    dango_id: str
    name: str
    position: int
    avatar_label: str


@dataclass(frozen=True)
class RaceViewState:
    positions: dict[str, int]
    stacks: dict[int, list[str]]
    devices: dict[int, str]
    current_actor: str | None
    last_roll: int | None
    event_log: tuple[str, ...]
    rankings: tuple[str, ...]
    live_rankings: tuple[str, ...]
    ranking_rows: tuple[RankingViewRow, ...]
    dango_names: dict[str, str]
    avatar_labels: dict[str, str]
    round_number: int
    finished: bool


@dataclass(frozen=True)
class SimulationResultRow:
    dango_id: str
    name: str
    wins: int
    win_rate: float
    average_rank: float
    weighted_score: float = 0.0
    rank: int = 0


def build_participant_cards(config: RaceConfig) -> list[ParticipantCardState]:
    cards: list[ParticipantCardState] = []
    for dango in config.dangos:
        is_boss = dango.is_boss
        cards.append(
            ParticipantCardState(
                dango_id=dango.id,
                name=dango.name,
                group=participant_group_label(dango.group),
                skill_note=dango.skill_note or "尚未設定技能摘要",
                selected=dango.default_selected,
                start_position=dango.start_position,
                is_boss=is_boss,
                boss_mode=BossMode.DISRUPTOR if is_boss else BossMode.NONE,
            ).normalized()
        )
    return cards


def avatar_label_for_name(name: str) -> str:
    stripped = name.strip()
    return stripped[0] if stripped else "?"


def participant_group_label(group: str) -> str:
    stripped = group.strip()
    return "" if stripped.lower() == "wip" else stripped


def dango_display_name(dango_id: str | None, dango_names: Mapping[str, str]) -> str:
    if dango_id is None:
        return "-"
    return dango_names.get(dango_id, "未知團子")


def device_display_name(device: str) -> str:
    return DEVICE_DISPLAY_NAMES.get(device, "未知裝置")


def track_cell_tooltip(*, index: int, device: str, is_midpoint: bool) -> str:
    labels = [device_display_name(device)]
    if is_midpoint:
        labels.append("中點")
    return f"格 {index} {' / '.join(labels)}"


def participant_selection_summary(cards: list[ParticipantCardState]) -> str:
    selected = [card.name for card in cards if card.selected and not card.is_boss]
    return f"已選 {len(selected)} 顆：{'、'.join(selected) or '尚未選擇'}"


def format_event_log_message(message: str) -> str:
    if message.startswith("第 ") or message.startswith("比賽結束"):
        return message
    return f"　　{message}"


def is_auto_play_control_enabled(*, single_race_active: bool, batch_running: bool) -> bool:
    return not batch_running


def is_seed_input_enabled(*, seed_mode: str, batch_controls_enabled: bool) -> bool:
    return batch_controls_enabled and seed_mode == "fixed"


def build_race_config_from_cards(config: RaceConfig, cards: list[ParticipantCardState]) -> RaceConfig:
    by_id = {card.dango_id: card.normalized() for card in cards}
    selected_dangos: list[DangoConfig] = []
    boss_ranked = False
    selected_general_count = 0
    for dango in config.dangos:
        card = by_id.get(dango.id)
        if card is None:
            continue
        if dango.is_boss:
            if card.selected and card.boss_mode is not BossMode.NONE:
                boss_ranked = card.boss_mode is BossMode.RANKED
                selected_dangos.append(replace(dango, ranked=boss_ranked, start_position=card.start_position))
            continue
        if card.selected:
            selected_dangos.append(replace(dango, start_position=card.start_position))
            selected_general_count += 1

    if selected_general_count < 1:
        raise ValueError("至少選擇 1 顆一般團子。")
    selected_ids = {dango.id for dango in selected_dangos}
    initial_stack_order = {
        card.dango_id: card.initial_stack_order
        for card in cards
        if card.dango_id in selected_ids and card.initial_stack_order is not None
    }
    first_round_order = {
        card.dango_id: card.first_round_order
        for card in cards
        if card.dango_id in selected_ids and card.first_round_order is not None
    }
    return replace(
        config,
        dangos=selected_dangos,
        boss_ranked=boss_ranked,
        initial_stack_order=initial_stack_order,
        first_round_order=first_round_order,
    )


def rank_simulation_rows(
    rows: list[SimulationResultRow],
    *,
    participant_count: int,
    win_weight: float = 0.70,
) -> list[SimulationResultRow]:
    rank_weight = 1.0 - win_weight
    denominator = max(1, participant_count - 1)
    scored: list[SimulationResultRow] = []
    for row in rows:
        rank_score = (participant_count - row.average_rank) / denominator
        rank_score = max(0.0, min(1.0, rank_score))
        weighted = row.win_rate * win_weight + rank_score * rank_weight
        scored.append(replace(row, weighted_score=weighted))

    scored.sort(key=lambda item: (-item.weighted_score, -item.win_rate, item.average_rank, item.name))
    return [replace(row, rank=index + 1) for index, row in enumerate(scored)]
