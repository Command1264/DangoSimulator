from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TooltipRect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class TooltipSize:
    width: int
    height: int


def choose_tooltip_position(
    target: TooltipRect,
    tooltip: TooltipSize,
    viewport: TooltipRect,
    *,
    gap: int = 8,
) -> tuple[int, int]:
    candidates = (
        (target.right + gap, target.y - tooltip.height - gap),
        (target.x - tooltip.width - gap, target.y - tooltip.height - gap),
        (target.x - tooltip.width - gap, target.bottom + gap),
        (target.right + gap, target.bottom + gap),
    )
    for x, y in candidates:
        if _fits(x, y, tooltip, viewport):
            return x, y
    return (
        _clamp(candidates[-1][0], viewport.x, viewport.right - tooltip.width),
        _clamp(candidates[-1][1], viewport.y, viewport.bottom - tooltip.height),
    )


def _fits(x: int, y: int, tooltip: TooltipSize, viewport: TooltipRect) -> bool:
    return (
        x >= viewport.x
        and y >= viewport.y
        and x + tooltip.width <= viewport.right
        and y + tooltip.height <= viewport.bottom
    )


def _clamp(value: int, lower: int, upper: int) -> int:
    if upper < lower:
        return lower
    return max(lower, min(value, upper))
