from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedIntegerText:
    text: str
    cursor_position: int
    value: int


@dataclass(frozen=True)
class SeparatorDeleteEdit:
    text: str
    digit_cursor: int


def format_grouped_int(value: int) -> str:
    return f"{value:,}"


def parse_grouped_int(text: str, *, default: int = 0) -> int:
    digits = _digits_only(text)
    if not digits:
        return default
    return int(digits)


def normalize_grouped_int_text(
    text: str,
    *,
    cursor_position: int,
    minimum: int,
    maximum: int,
    digit_cursor: int | None = None,
) -> NormalizedIntegerText:
    digits = _digits_only(text)
    if not digits:
        value = minimum
        formatted = format_grouped_int(value)
        return NormalizedIntegerText(text=formatted, cursor_position=len(formatted), value=value)

    requested_value = int(digits)
    value = max(minimum, min(maximum, requested_value))
    formatted = format_grouped_int(value)
    if digit_cursor is None:
        digit_cursor = _count_digits(text[:cursor_position])
    if value != requested_value:
        digit_cursor = len(str(value))
    cursor = cursor_position_for_digit_count(formatted, digit_cursor)
    return NormalizedIntegerText(text=formatted, cursor_position=cursor, value=value)


def apply_group_separator_delete(text: str, *, cursor_position: int, key: str) -> SeparatorDeleteEdit | None:
    if key == "backspace":
        separator_index = cursor_position - 1
        if separator_index < 0 or separator_index >= len(text) or text[separator_index] != ",":
            return None
        target_index = _previous_digit_index(text, separator_index)
        if target_index is None:
            return None
        return SeparatorDeleteEdit(
            text=text[:target_index] + text[target_index + 1 :],
            digit_cursor=_count_digits(text[:target_index]),
        )

    if key == "delete":
        separator_index = cursor_position
        if separator_index < 0 or separator_index >= len(text) or text[separator_index] != ",":
            return None
        target_index = _next_digit_index(text, separator_index + 1)
        if target_index is None:
            return None
        return SeparatorDeleteEdit(
            text=text[:target_index] + text[target_index + 1 :],
            digit_cursor=_count_digits(text[:cursor_position]),
        )

    return None


def cursor_position_for_digit_count(text: str, digit_count: int) -> int:
    if digit_count <= 0:
        return 0
    seen = 0
    for index, character in enumerate(text):
        if character.isdigit():
            seen += 1
        if seen >= digit_count:
            return index + 1
    return len(text)


def _digits_only(text: str) -> str:
    return "".join(character for character in text if character.isdigit())


def _count_digits(text: str) -> int:
    return sum(1 for character in text if character.isdigit())


def _previous_digit_index(text: str, start_index: int) -> int | None:
    for index in range(start_index - 1, -1, -1):
        if text[index].isdigit():
            return index
    return None


def _next_digit_index(text: str, start_index: int) -> int | None:
    for index in range(start_index, len(text)):
        if text[index].isdigit():
            return index
    return None
