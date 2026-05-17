from __future__ import annotations

from dangosim.gui.number_formatting import (
    apply_group_separator_delete,
    format_grouped_int,
    normalize_grouped_int_text,
)


def test_format_grouped_int_uses_thousands_commas() -> None:
    assert format_grouped_int(1) == "1"
    assert format_grouped_int(1000) == "1,000"
    assert format_grouped_int(99999999) == "99,999,999"


def test_normalize_grouped_int_text_formats_on_each_edit_and_preserves_digit_cursor() -> None:
    normalized = normalize_grouped_int_text("1000", cursor_position=4, minimum=1, maximum=99999999)

    assert normalized.text == "1,000"
    assert normalized.cursor_position == 5
    assert normalized.value == 1000

    middle_edit = normalize_grouped_int_text("1234", cursor_position=2, minimum=1, maximum=99999999)

    assert middle_edit.text == "1,234"
    assert middle_edit.cursor_position == 3
    assert middle_edit.value == 1234


def test_normalize_grouped_int_text_clamps_to_allowed_range() -> None:
    normalized = normalize_grouped_int_text("999999999", cursor_position=9, minimum=1, maximum=99999999)

    assert normalized.text == "99,999,999"
    assert normalized.cursor_position == 10
    assert normalized.value == 99999999


def test_backspace_on_group_separator_deletes_digit_to_the_left() -> None:
    edit = apply_group_separator_delete("12,345", cursor_position=3, key="backspace")

    assert edit is not None
    normalized = normalize_grouped_int_text(
        edit.text,
        cursor_position=0,
        minimum=1,
        maximum=99999999,
        digit_cursor=edit.digit_cursor,
        cursor_from_right=edit.cursor_from_right,
    )

    assert normalized.text == "1,345"
    assert normalized.cursor_position == 1
    assert normalized.value == 1345


def test_delete_on_group_separator_deletes_digit_to_the_right() -> None:
    edit = apply_group_separator_delete("12,345", cursor_position=2, key="delete")

    assert edit is not None
    normalized = normalize_grouped_int_text(
        edit.text,
        cursor_position=0,
        minimum=1,
        maximum=99999999,
        digit_cursor=edit.digit_cursor,
        cursor_from_right=edit.cursor_from_right,
    )

    assert normalized.text == "1,245"
    assert normalized.cursor_position == 2
    assert normalized.value == 1245


def test_group_separator_delete_ignores_regular_digit_deletion() -> None:
    assert apply_group_separator_delete("12,345", cursor_position=2, key="backspace") is None
    assert apply_group_separator_delete("12,345", cursor_position=3, key="delete") is None
