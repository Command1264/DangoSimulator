from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BettingFormula:
    wrong_refund_rate: float = 0.8
    rank_rewards: dict[int, float] = field(default_factory=lambda: {1: 1.0})

    def multiplier_for_rank(self, rank: int) -> float:
        return self.rank_rewards.get(rank, self.wrong_refund_rate)


@dataclass(frozen=True)
class Bet:
    race_id: str
    dango_id: str
    amount: int
    dark_horse_value: float


@dataclass(frozen=True)
class SettlementEntry:
    bet: Bet
    rank: int | None
    reward: int


@dataclass(frozen=True)
class SettlementResult:
    balance: int
    entries: dict[str, SettlementEntry]


class BetLedger:
    def __init__(self, initial_popularity: int, formula: BettingFormula) -> None:
        if initial_popularity < 0:
            raise ValueError("Initial popularity must be non-negative.")
        self._balance = initial_popularity
        self._formula = formula
        self._bets: list[Bet] = []

    @property
    def balance(self) -> int:
        return self._balance

    def place_bet(self, race_id: str, dango_id: str, amount: int, dark_horse_value: float) -> None:
        if amount <= 0:
            raise ValueError("Bet amount must be positive.")
        if amount > self._balance:
            raise ValueError("Insufficient popularity balance.")
        if dark_horse_value <= 0:
            raise ValueError("Dark horse value must be positive.")

        self._balance -= amount
        self._bets.append(Bet(race_id, dango_id, amount, dark_horse_value))

    def settle(self, race_id: str, rankings: list[str]) -> SettlementResult:
        rank_by_dango = {dango_id: index + 1 for index, dango_id in enumerate(rankings)}
        entries: dict[str, SettlementEntry] = {}
        for bet in [bet for bet in self._bets if bet.race_id == race_id]:
            rank = rank_by_dango.get(bet.dango_id)
            multiplier = self._formula.multiplier_for_rank(rank) if rank is not None else self._formula.wrong_refund_rate
            reward = int(round(bet.amount * bet.dark_horse_value * multiplier))
            self._balance += reward
            entries[bet.dango_id] = SettlementEntry(bet=bet, rank=rank, reward=reward)
        return SettlementResult(balance=self._balance, entries=entries)
