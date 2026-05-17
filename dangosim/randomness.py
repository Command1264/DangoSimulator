from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import Enum

MAX_SEED_EXCLUSIVE = 2**64


class SeedMode(str, Enum):
    FIXED = "fixed"
    SYSTEM = "system"


@dataclass(frozen=True)
class ResolvedSeed:
    mode: SeedMode
    seed: int


def resolve_seed(
    *,
    mode: SeedMode,
    requested_seed: int | None,
    config_seed: int | None,
) -> ResolvedSeed:
    if mode is SeedMode.SYSTEM:
        return ResolvedSeed(mode=mode, seed=secrets.randbits(64))
    seed = requested_seed if requested_seed is not None else config_seed if config_seed is not None else 0
    if seed < 0 or seed >= MAX_SEED_EXCLUSIVE:
        raise ValueError(f"seed must be between 0 and {MAX_SEED_EXCLUSIVE - 1}.")
    return ResolvedSeed(mode=SeedMode.FIXED, seed=seed)
