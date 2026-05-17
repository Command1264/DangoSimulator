from __future__ import annotations

from dangosim.gui.batch_estimation import (
    build_batch_estimate_confirmation_message,
    estimate_seconds_from_sample,
    estimate_sample_runs,
)


def test_estimate_sample_runs_uses_requested_runs_for_small_batches() -> None:
    assert estimate_sample_runs(1) == 1
    assert estimate_sample_runs(8) == 8
    assert estimate_sample_runs(10) == 10


def test_estimate_sample_runs_increases_for_large_batches_with_cap() -> None:
    assert estimate_sample_runs(1000) == 10
    assert estimate_sample_runs(100_000) == 100
    assert estimate_sample_runs(99_999_999) == 200


def test_estimate_seconds_from_sample_scales_linearly() -> None:
    assert estimate_seconds_from_sample(elapsed_seconds=2.0, sample_runs=100, total_runs=1000) == 20.0
    assert estimate_seconds_from_sample(elapsed_seconds=2.0, sample_runs=0, total_runs=1000) == 0.0


def test_batch_estimate_confirmation_message_asks_before_starting() -> None:
    message = build_batch_estimate_confirmation_message(
        sample_runs=10000,
        worker_count=16,
        total_runs=99999999,
        duration_text="20 秒",
    )

    assert "已先試跑 10,000 場。" in message
    assert "正式模擬會使用 16 個 worker。" in message
    assert "預估 99,999,999 場約需 20 秒。" in message
    assert "是否開始正式模擬？" in message
