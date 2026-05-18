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

    regular_position_set = set(regular_positions)
    if boss_position in regular_position_set:
        return False

    positions_ahead = set(_positions_before_finish_in_boss_direction(boss_position, finish=finish, length=length))
    return positions_ahead.isdisjoint(regular_position_set)


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
