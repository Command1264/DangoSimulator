from __future__ import annotations

import json
from pathlib import Path

import pytest

from dangosim.cli.main import main
from dangosim.core.batch import _pack_config, _unpack_config, resolve_worker_count, simulate_many
from dangosim.core.config_loader import load_race_config
from dangosim.core.models import DangoConfig, RaceConfig, TrackConfig
from dangosim.randomness import SeedMode


def _default_config():
    return load_race_config(Path("data/default_race.json").read_text(encoding="utf-8"))


def test_parallel_simulate_many_matches_single_worker_with_fixed_seed() -> None:
    config = _default_config()

    single = simulate_many(config, runs=24, seed=20260518, seed_mode=SeedMode.FIXED, workers=1)
    parallel = simulate_many(
        config,
        runs=24,
        seed=20260518,
        seed_mode=SeedMode.FIXED,
        workers=2,
        chunk_size=4,
    )

    assert parallel["completed_runs"] == single["completed_runs"] == 24
    assert parallel["cancelled"] is False
    assert parallel["results"] == single["results"]


def test_parallel_worker_config_preserves_track_midpoint() -> None:
    config = RaceConfig(
        track=TrackConfig(length=10, finish=10, midpoint=6),
        dangos=[DangoConfig(id="a", name="A", start_position=1)],
        seed=7,
    )

    worker_config = _pack_config(config)
    unpacked = _unpack_config(worker_config, seed=8)

    assert unpacked.track.midpoint == 6


def test_parallel_worker_config_preserves_participant_order_overrides() -> None:
    config = RaceConfig(
        track=TrackConfig(length=10, finish=10),
        dangos=[
            DangoConfig(id="a", name="A", start_position=1),
            DangoConfig(id="b", name="B", start_position=1),
        ],
        seed=7,
        initial_stack_order={"b": 1, "a": 2},
        first_round_order={"a": 1, "b": 2},
    )

    worker_config = _pack_config(config)
    unpacked = _unpack_config(worker_config, seed=8)

    assert unpacked.initial_stack_order == {"b": 1, "a": 2}
    assert unpacked.first_round_order == {"a": 1, "b": 2}


def test_parallel_simulate_many_reports_chunk_progress_to_completion() -> None:
    progress: list[tuple[int, int]] = []

    result = simulate_many(
        _default_config(),
        runs=10,
        seed=99,
        seed_mode=SeedMode.FIXED,
        workers=2,
        chunk_size=2,
        progress_callback=lambda completed, total: progress.append((completed, total)),
    )

    assert result["completed_runs"] == 10
    assert progress[-1] == (10, 10)
    assert progress == sorted(progress)


def test_parallel_simulate_many_can_cancel_before_scheduling_work() -> None:
    result = simulate_many(
        _default_config(),
        runs=10,
        seed=99,
        seed_mode=SeedMode.FIXED,
        workers=2,
        chunk_size=2,
        cancel_requested=lambda: True,
    )

    assert result["completed_runs"] == 0
    assert result["cancelled"] is True


def test_simulate_many_counts_ranked_boss_last_when_race_finishes_before_boss_can_act() -> None:
    result = simulate_many(
        RaceConfig(
            track=TrackConfig(length=10, finish=10),
            dangos=[
                DangoConfig(id="a", name="A", start_position=8),
                DangoConfig(id="boss", name="布大王", start_position=10, is_boss=True, ranked=True),
            ],
            boss_ranked=True,
            seed=7,
        ),
        runs=1,
        seed=7,
        seed_mode=SeedMode.FIXED,
        workers=1,
    )

    rows = {str(item["dango_id"]): item for item in result["results"]}  # type: ignore[index]
    assert rows["a"]["average_rank"] == 1
    assert rows["boss"]["average_rank"] == 2


def test_resolve_worker_count_accepts_auto_full_and_positive_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dangosim.core.batch.os.cpu_count", lambda: 12)

    assert resolve_worker_count(1, runs=100) == 1
    assert resolve_worker_count("auto", runs=100) == 8
    assert resolve_worker_count("full", runs=100) == 12
    assert resolve_worker_count("2", runs=100) == 2


def test_resolve_worker_count_never_exceeds_cpu_count_or_run_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dangosim.core.batch.os.cpu_count", lambda: 8)

    assert resolve_worker_count("99", runs=100) == 8
    assert resolve_worker_count("full", runs=3) == 3


def test_cli_workers_option_keeps_fixed_seed_results_reproducible(tmp_path: Path) -> None:
    single_path = tmp_path / "single.json"
    parallel_path = tmp_path / "parallel.json"

    assert main(
        [
            "simulate",
            "--config",
            "data/default_race.json",
            "--runs",
            "12",
            "--seed",
            "20260518",
            "--workers",
            "1",
            "--out",
            str(single_path),
        ]
    ) == 0
    assert main(
        [
            "simulate",
            "--config",
            "data/default_race.json",
            "--runs",
            "12",
            "--seed",
            "20260518",
            "--workers",
            "2",
            "--out",
            str(parallel_path),
        ]
    ) == 0

    assert json.loads(parallel_path.read_text(encoding="utf-8"))["results"] == json.loads(
        single_path.read_text(encoding="utf-8")
    )["results"]
