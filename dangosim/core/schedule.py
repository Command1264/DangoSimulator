from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time


@dataclass(frozen=True)
class RaceSupportWindow:
    opens_at: datetime
    closes_at: datetime
    race_starts_at: datetime

    @classmethod
    def for_race_date(cls, race_date: date, *, previous_race_end_at: datetime) -> "RaceSupportWindow":
        race_starts_at = datetime.combine(race_date, time(hour=21, minute=0))
        closes_at = datetime.combine(race_date, time(hour=20, minute=30))
        if previous_race_end_at >= closes_at:
            raise ValueError("Previous race end must be before support close time.")
        return cls(opens_at=previous_race_end_at, closes_at=closes_at, race_starts_at=race_starts_at)

    def is_open(self, moment: datetime) -> bool:
        return self.opens_at <= moment < self.closes_at
