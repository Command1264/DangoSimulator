from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class DeviceType(str, Enum):
    BLANK = "blank"
    ADVANCE = "advance"
    BLOCK = "block"
    TIME_RIFT = "time_rift"


@dataclass(frozen=True)
class TrackConfig:
    length: int
    finish: int
    devices: Mapping[int, DeviceType] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.length < 2:
            raise ValueError("Track length must be at least 2.")
        if not 1 <= self.finish <= self.length:
            raise ValueError("Finish must be inside the track.")

        normalized: dict[int, DeviceType] = {}
        for position, device in self.devices.items():
            if not 1 <= int(position) <= self.length:
                raise ValueError(f"Device position {position} is outside the track.")
            normalized[int(position)] = device if isinstance(device, DeviceType) else DeviceType(str(device))
        object.__setattr__(self, "devices", MappingProxyType(normalized))

    def device_at(self, position: int) -> DeviceType:
        return self.devices.get(position, DeviceType.BLANK)


@dataclass(frozen=True)
class AbilityCondition:
    type: str


@dataclass(frozen=True)
class AbilityAction:
    type: str
    value: int | float | str | None = None


@dataclass(frozen=True)
class AbilityConfig:
    id: str
    trigger: str
    conditions: tuple[AbilityCondition, ...] = ()
    actions: tuple[AbilityAction, ...] = ()
    probability: float = 1.0
    once_per_race: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Ability id is required.")
        if not 0 <= self.probability <= 1:
            raise ValueError("Ability probability must be between 0 and 1.")


@dataclass(frozen=True)
class DangoConfig:
    id: str
    name: str
    start_position: int
    is_boss: bool = False
    ranked: bool = True
    abilities: tuple[AbilityConfig, ...] = ()
    group: str = "預設"
    skill_note: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Dango id is required.")
        if not self.name:
            raise ValueError("Dango name is required.")


@dataclass(frozen=True)
class RaceConfig:
    track: TrackConfig
    dangos: list[DangoConfig]
    seed: int | None = None
    boss_ranked: bool = False

    def __post_init__(self) -> None:
        if not self.dangos:
            raise ValueError("Race must include at least one dango.")
        seen: set[str] = set()
        for dango in self.dangos:
            if dango.id in seen:
                raise ValueError(f"Duplicate dango id: {dango.id}")
            if not 1 <= dango.start_position <= self.track.length:
                raise ValueError(f"Start position for {dango.id} is outside the track.")
            seen.add(dango.id)


@dataclass(frozen=True)
class EventRecord:
    event_type: str
    message: str
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MoveResult:
    dango_id: str
    roll: int
    from_position: int
    to_position: int
    carried: tuple[str, ...]
    device_triggered: DeviceType = DeviceType.BLANK
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RaceSnapshot:
    positions: Mapping[str, int]
    stacks: Mapping[int, list[str]]
    event_log: tuple[EventRecord, ...]
    rankings: tuple[str, ...]
    finished: bool
