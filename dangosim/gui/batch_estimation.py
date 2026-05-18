from __future__ import annotations

from dangosim.gui.number_formatting import format_grouped_int

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


def build_batch_estimate_confirmation_message(
    *,
    sample_runs: int,
    worker_count: int,
    total_runs: int,
    duration_text: str,
) -> str:
    return (
        f"已先試跑 {format_grouped_int(sample_runs)} 場。\n"
        f"正式模擬會使用 {format_grouped_int(worker_count)} 個 worker。\n"
        f"預估 {format_grouped_int(total_runs)} 場約需 {duration_text}。\n\n"
        "是否開始正式模擬？"
    )
