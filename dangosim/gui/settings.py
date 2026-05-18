from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dangosim.gui.view_models import BossMode, ParticipantCardState

SETTINGS_VERSION = 1
MIN_SPEED_MS = 150
MAX_SPEED_MS = 2000
MIN_BATCH_RUNS = 1
MAX_BATCH_RUNS = 99_999_999
SORT_MODES = ("綜合分數", "勝率", "平均名次")
SEED_MODES = ("fixed", "system")


@dataclass(frozen=True)
class ParticipantOverrideSettings:
    dango_id: str
    selected: bool = False
    start_position: int | None = None
    initial_stack_order: int | None = None
    first_round_order: int | None = None


@dataclass(frozen=True)
class ParticipantSettings:
    selected_dango_ids: tuple[str, ...] = ()
    boss_mode: str = BossMode.DISRUPTOR.value
    participant_overrides: tuple[ParticipantOverrideSettings, ...] = ()


@dataclass(frozen=True)
class SingleRaceSettings:
    speed_ms: int = 700
    auto_play: bool = False


@dataclass(frozen=True)
class BatchSimulationSettings:
    runs: int = 1000
    seed_mode: str = "fixed"
    seed: str = "20260517"
    sort_mode: str = "綜合分數"
    workers: str = "auto"


@dataclass(frozen=True)
class UserSettings:
    version: int = SETTINGS_VERSION
    participants: ParticipantSettings = field(default_factory=ParticipantSettings)
    single_race: SingleRaceSettings = field(default_factory=SingleRaceSettings)
    batch_simulation: BatchSimulationSettings = field(default_factory=BatchSimulationSettings)


class UserSettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def default(cls) -> "UserSettingsStore":
        configured_path = os.environ.get("DANGOSIM_SETTINGS_PATH")
        if configured_path:
            return cls(Path(configured_path))
        appdata = os.environ.get("APPDATA")
        base_dir = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return cls(base_dir / "DangoSimulator" / "settings.json")

    def load(self) -> UserSettings:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return UserSettings()
        if not isinstance(payload, dict):
            return UserSettings()
        return _settings_from_payload(payload)

    def save(self, settings: UserSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(_settings_to_payload(settings), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def apply_settings_to_cards(
    cards: list[ParticipantCardState],
    settings: UserSettings,
) -> list[ParticipantCardState]:
    selected_ids = set(settings.participants.selected_dango_ids)
    boss_mode = _boss_mode(settings.participants.boss_mode)
    max_position = max((card.start_position for card in cards), default=1)
    overrides = {
        override.dango_id: override
        for override in settings.participants.participant_overrides
    }
    if not selected_ids:
        return [
            _apply_participant_override(
                card.with_updates(boss_mode=boss_mode)
                if card.is_boss
                else card,
                overrides.get(card.dango_id),
                max_position=max_position,
            )
            for card in cards
        ]
    known_general_ids = {card.dango_id for card in cards if not card.is_boss}
    selected_ids = selected_ids & known_general_ids
    if not selected_ids:
        return [
            _apply_participant_override(
                card.with_updates(boss_mode=boss_mode)
                if card.is_boss
                else card,
                overrides.get(card.dango_id),
                max_position=max_position,
            )
            for card in cards
        ]
    return [
        _apply_participant_override(
            card.with_updates(selected=True, boss_mode=boss_mode),
            overrides.get(card.dango_id),
            max_position=max_position,
        )
        if card.is_boss
        else _apply_participant_override(
            card.with_updates(selected=card.dango_id in selected_ids),
            overrides.get(card.dango_id),
            max_position=max_position,
        )
        for card in cards
    ]


def _settings_from_payload(payload: dict[str, Any]) -> UserSettings:
    participants = _dict_value(payload, "participants")
    single_race = _dict_value(payload, "single_race")
    batch_simulation = _dict_value(payload, "batch_simulation")
    return UserSettings(
        participants=ParticipantSettings(
            selected_dango_ids=_string_tuple(participants.get("selected_dango_ids")),
            boss_mode=_boss_mode(participants.get("boss_mode")).value,
            participant_overrides=_participant_overrides(participants.get("participant_overrides")),
        ),
        single_race=SingleRaceSettings(
            speed_ms=_bounded_int(single_race.get("speed_ms"), MIN_SPEED_MS, MAX_SPEED_MS, 700),
            auto_play=_bool_value(single_race.get("auto_play"), False),
        ),
        batch_simulation=BatchSimulationSettings(
            runs=_bounded_int(batch_simulation.get("runs"), MIN_BATCH_RUNS, MAX_BATCH_RUNS, 1000),
            seed_mode=_choice(batch_simulation.get("seed_mode"), SEED_MODES, "fixed"),
            seed=str(batch_simulation.get("seed", "20260517")),
            sort_mode=_choice(batch_simulation.get("sort_mode"), SORT_MODES, "綜合分數"),
            workers=_worker_setting(batch_simulation.get("workers")),
        ),
    )


def _settings_to_payload(settings: UserSettings) -> dict[str, Any]:
    payload = asdict(settings)
    payload["participants"]["selected_dango_ids"] = list(settings.participants.selected_dango_ids)
    payload["participants"]["participant_overrides"] = [
        asdict(override)
        for override in settings.participants.participant_overrides
    ]
    return payload


def _apply_participant_override(
    card: ParticipantCardState,
    override: ParticipantOverrideSettings | None,
    *,
    max_position: int,
) -> ParticipantCardState:
    if override is None:
        return card
    start_position = (
        override.start_position
        if override.start_position is not None and 1 <= override.start_position <= max_position
        else card.start_position
    )
    updated = card.with_updates(
        selected=override.selected,
        start_position=start_position,
    )
    return updated.with_order_updates(
        initial_stack_order=override.initial_stack_order,
        first_round_order=override.first_round_order,
    )


def _dict_value(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _participant_overrides(value: Any) -> tuple[ParticipantOverrideSettings, ...]:
    if not isinstance(value, list):
        return ()
    overrides: list[ParticipantOverrideSettings] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        dango_id = item.get("dango_id")
        if not isinstance(dango_id, str) or not dango_id:
            continue
        overrides.append(
            ParticipantOverrideSettings(
                dango_id=dango_id,
                selected=_bool_value(item.get("selected"), False),
                start_position=_optional_positive_int(item.get("start_position")),
                initial_stack_order=_optional_positive_int(item.get("initial_stack_order")),
                first_round_order=_optional_positive_int(item.get("first_round_order")),
            )
        )
    return tuple(overrides)


def _boss_mode(value: Any) -> BossMode:
    try:
        return BossMode(str(value))
    except ValueError:
        return BossMode.DISRUPTOR


def _bounded_int(value: Any, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _choice(value: Any, allowed: tuple[str, ...], default: str) -> str:
    text = str(value)
    return text if text in allowed else default


def _bool_value(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 1 else None


def _worker_setting(value: Any) -> str:
    if value in {"auto", "full"}:
        return str(value)
    try:
        workers = int(value)
    except (TypeError, ValueError):
        return "auto"
    if workers < 1 or workers > _available_worker_count():
        return "auto"
    return str(workers)


def _available_worker_count() -> int:
    return max(1, os.cpu_count() or 1)
