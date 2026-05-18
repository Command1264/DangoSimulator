from __future__ import annotations

from dangosim.core.boss_rules import should_boss_return_to_finish


def test_boss_stays_when_regular_is_ahead_before_finish_in_boss_direction() -> None:
    assert (
        should_boss_return_to_finish(
            boss_position=8,
            finish=12,
            length=12,
            regular_positions=[6],
        )
        is False
    )


def test_boss_returns_when_no_regular_is_ahead_before_finish_in_boss_direction() -> None:
    assert (
        should_boss_return_to_finish(
            boss_position=8,
            finish=12,
            length=12,
            regular_positions=[9, 10],
        )
        is True
    )


def test_boss_does_not_return_when_already_at_finish() -> None:
    assert (
        should_boss_return_to_finish(
            boss_position=12,
            finish=12,
            length=12,
            regular_positions=[6],
        )
        is False
    )
