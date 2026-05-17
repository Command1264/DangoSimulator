from __future__ import annotations

MIN_SAMPLE_RUNS = 10
MAX_SAMPLE_RUNS = 200
LARGE_BATCH_DIVISOR = 1000


def estimate_sample_runs(total_runs: int) -> int:
    if total_runs <= 0:
        return 0
    scaled_sample = total_runs // LARGE_BATCH_DIVISOR
    target_sample = max(MIN_SAMPLE_RUNS, scaled_sample)
    return min(total_runs, min(MAX_SAMPLE_RUNS, target_sample))


def estimate_seconds_from_sample(
    *,
    elapsed_seconds: float,
    sample_runs: int,
    total_runs: int,
) -> float:
    if sample_runs <= 0 or total_runs <= 0:
        return 0.0
    return (elapsed_seconds / sample_runs) * total_runs
