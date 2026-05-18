from __future__ import annotations

from collections.abc import Iterable


def should_boss_return_to_finish(
    *,
    boss_position: int,
    finish: int,
    length: int,
    regular_positions: Iterable[int],
) -> bool:
    if boss_position == finish:
        return False

    positions_ahead = set(_positions_before_finish_in_boss_direction(boss_position, finish=finish, length=length))
    return positions_ahead.isdisjoint(regular_positions)


def _positions_before_finish_in_boss_direction(
    boss_position: int,
    *,
    finish: int,
    length: int,
) -> tuple[int, ...]:
    positions: list[int] = []
    position = boss_position
    while True:
        position -= 1
        if position < 1:
            position = length
        if position == finish:
            return tuple(positions)
        positions.append(position)
