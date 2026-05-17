from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from dangosim.core.models import DangoConfig, RaceConfig


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
    ) -> "ParticipantCardState":
        return replace(
            self,
            selected=self.selected if selected is None else selected,
            boss_mode=self.boss_mode if boss_mode is None else boss_mode,
        ).normalized()


@dataclass(frozen=True)
class RaceViewState:
    positions: dict[str, int]
    stacks: dict[int, list[str]]
    devices: dict[int, str]
    current_actor: str | None
    last_roll: int | None
    event_log: tuple[str, ...]
    rankings: tuple[str, ...]
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
                group=dango.group,
                skill_note=dango.skill_note or "尚未設定技能摘要",
                selected=True,
                is_boss=is_boss,
                boss_mode=BossMode.DISRUPTOR if is_boss else BossMode.NONE,
            ).normalized()
        )
    return cards


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
                selected_dangos.append(replace(dango, ranked=boss_ranked))
            continue
        if card.selected:
            selected_dangos.append(dango)
            selected_general_count += 1

    if selected_general_count < 1:
        raise ValueError("至少選擇 1 顆一般團子。")
    return replace(config, dangos=selected_dangos, boss_ranked=boss_ranked)


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
