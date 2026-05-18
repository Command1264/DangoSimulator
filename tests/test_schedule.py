from __future__ import annotations

from datetime import date, datetime

from dangosim.core.schedule import RaceSupportWindow


def test_support_window_closes_half_hour_before_21_race_start() -> None:
    previous_race_end = datetime(2026, 5, 17, 21, 10)

    window = RaceSupportWindow.for_race_date(date(2026, 5, 18), previous_race_end_at=previous_race_end)

    assert window.opens_at == previous_race_end
    assert window.closes_at == datetime(2026, 5, 18, 20, 30)
    assert window.race_starts_at == datetime(2026, 5, 18, 21, 0)
    assert window.is_open(datetime(2026, 5, 18, 20, 29))
    assert not window.is_open(datetime(2026, 5, 18, 20, 30))
