from __future__ import annotations

from dangosim.gui.tooltips import TooltipRect, TooltipSize, choose_tooltip_position


def test_tooltip_position_prefers_top_right_when_it_fits() -> None:
    target = TooltipRect(x=40, y=40, width=10, height=10)
    tooltip = TooltipSize(width=20, height=10)
    viewport = TooltipRect(x=0, y=0, width=100, height=100)

    assert choose_tooltip_position(target, tooltip, viewport) == (58, 22)


def test_tooltip_position_falls_back_to_top_left_before_bottom_slots() -> None:
    target = TooltipRect(x=70, y=40, width=20, height=10)
    tooltip = TooltipSize(width=20, height=10)
    viewport = TooltipRect(x=0, y=0, width=100, height=100)

    assert choose_tooltip_position(target, tooltip, viewport) == (42, 22)


def test_tooltip_position_falls_back_to_bottom_left_when_top_slots_do_not_fit() -> None:
    target = TooltipRect(x=70, y=5, width=20, height=10)
    tooltip = TooltipSize(width=20, height=10)
    viewport = TooltipRect(x=0, y=0, width=100, height=100)

    assert choose_tooltip_position(target, tooltip, viewport) == (42, 23)


def test_tooltip_position_clamps_when_no_slot_fits() -> None:
    target = TooltipRect(x=50, y=45, width=10, height=10)
    tooltip = TooltipSize(width=120, height=80)
    viewport = TooltipRect(x=0, y=0, width=100, height=70)

    assert choose_tooltip_position(target, tooltip, viewport) == (0, 0)
