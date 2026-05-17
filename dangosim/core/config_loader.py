from __future__ import annotations

import json
from typing import Any

from dangosim.core.models import (
    AbilityAction,
    AbilityCondition,
    AbilityConfig,
    DeviceType,
    DangoConfig,
    RaceConfig,
    TrackConfig,
)


class ConfigValidationError(ValueError):
    pass


ALLOWED_ABILITY_TRIGGERS = {"before_move"}
ALLOWED_ABILITY_CONDITIONS = {"always"}
ALLOWED_ABILITY_ACTIONS = {"add_steps"}


def load_race_config(raw_json: str) -> RaceConfig:
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ConfigValidationError(f"Invalid JSON: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise ConfigValidationError("Race config must be a JSON object.")

    track_payload = _require_object(payload, "track")
    length = _require_int(track_payload, "length")
    finish = int(track_payload.get("finish", length))
    devices = _parse_devices(track_payload.get("devices", []), length)

    dangos_payload = payload.get("dangos")
    if not isinstance(dangos_payload, list) or not dangos_payload:
        raise ConfigValidationError("Field 'dangos' must be a non-empty array.")

    dangos = [_parse_dango(item, length) for item in dangos_payload]
    try:
        return RaceConfig(
            track=TrackConfig(length=length, finish=finish, devices=devices),
            dangos=dangos,
            seed=payload.get("seed"),
            boss_ranked=bool(payload.get("boss_ranked", False)),
        )
    except ValueError as exc:
        raise ConfigValidationError(str(exc)) from exc


def _parse_devices(raw_devices: Any, length: int) -> dict[int, DeviceType]:
    if raw_devices is None:
        return {}
    if not isinstance(raw_devices, list):
        raise ConfigValidationError("Field 'devices' must be an array.")

    devices: dict[int, DeviceType] = {}
    for raw in raw_devices:
        if not isinstance(raw, dict):
            raise ConfigValidationError("Each device must be an object.")
        position = _require_int(raw, "position")
        if not 1 <= position <= length:
            raise ConfigValidationError(f"Device position {position} is outside the track.")
        device_type = raw.get("type")
        try:
            devices[position] = DeviceType(str(device_type))
        except ValueError as exc:
            raise ConfigValidationError(f"Unknown device type: {device_type}") from exc
    return devices


def _parse_dango(raw: Any, length: int) -> DangoConfig:
    if not isinstance(raw, dict):
        raise ConfigValidationError("Each dango must be an object.")
    start_position = _require_int(raw, "start_position")
    if not 1 <= start_position <= length:
        raise ConfigValidationError(f"Dango start position {start_position} is outside the track.")
    try:
        return DangoConfig(
            id=str(raw["id"]),
            name=str(raw["name"]),
            start_position=start_position,
            is_boss=bool(raw.get("is_boss", False)),
            ranked=bool(raw.get("ranked", True)),
            abilities=tuple(_parse_abilities(raw.get("abilities", []))),
            group=str(raw.get("group", "預設")),
            skill_note=str(raw.get("ability_note", raw.get("skill_note", ""))),
        )
    except KeyError as exc:
        raise ConfigValidationError(f"Missing dango field: {exc.args[0]}") from exc
    except ValueError as exc:
        raise ConfigValidationError(str(exc)) from exc


def _require_object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ConfigValidationError(f"Field '{key}' must be an object.")
    return value


def _parse_abilities(raw_abilities: Any) -> list[AbilityConfig]:
    if raw_abilities is None:
        return []
    if not isinstance(raw_abilities, list):
        raise ConfigValidationError("Field 'abilities' must be an array.")

    abilities: list[AbilityConfig] = []
    for raw in raw_abilities:
        if not isinstance(raw, dict):
            raise ConfigValidationError("Each ability must be an object.")
        ability_id = str(raw.get("id", ""))
        trigger = str(raw.get("trigger", ""))
        if trigger not in ALLOWED_ABILITY_TRIGGERS:
            raise ConfigValidationError(f"Unknown ability trigger: {trigger}")
        conditions = tuple(_parse_conditions(raw.get("conditions", [{"type": "always"}])))
        actions = tuple(_parse_actions(raw.get("actions", [])))
        if not actions:
            raise ConfigValidationError(f"Ability {ability_id} must include at least one action.")
        try:
            abilities.append(
                AbilityConfig(
                    id=ability_id,
                    trigger=trigger,
                    conditions=conditions,
                    actions=actions,
                    probability=float(raw.get("probability", 1.0)),
                    once_per_race=bool(raw.get("once_per_race", False)),
                )
            )
        except ValueError as exc:
            raise ConfigValidationError(str(exc)) from exc
    return abilities


def _parse_conditions(raw_conditions: Any) -> list[AbilityCondition]:
    if not isinstance(raw_conditions, list):
        raise ConfigValidationError("Ability conditions must be an array.")
    conditions: list[AbilityCondition] = []
    for raw in raw_conditions:
        if not isinstance(raw, dict):
            raise ConfigValidationError("Each ability condition must be an object.")
        condition_type = str(raw.get("type", ""))
        if condition_type not in ALLOWED_ABILITY_CONDITIONS:
            raise ConfigValidationError(f"Unknown ability condition: {condition_type}")
        conditions.append(AbilityCondition(type=condition_type))
    return conditions


def _parse_actions(raw_actions: Any) -> list[AbilityAction]:
    if not isinstance(raw_actions, list):
        raise ConfigValidationError("Ability actions must be an array.")
    actions: list[AbilityAction] = []
    for raw in raw_actions:
        if not isinstance(raw, dict):
            raise ConfigValidationError("Each ability action must be an object.")
        action_type = str(raw.get("type", ""))
        if action_type not in ALLOWED_ABILITY_ACTIONS:
            raise ConfigValidationError(f"Unknown ability action: {action_type}")
        actions.append(AbilityAction(type=action_type, value=raw.get("value")))
    return actions


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ConfigValidationError(f"Field '{key}' must be an integer.")
    return value
