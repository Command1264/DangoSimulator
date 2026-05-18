from __future__ import annotations

import math
import os
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace

from dangosim.core.models import DangoConfig, DeviceType, RaceConfig, TrackConfig
from dangosim.core.simulator import RaceSimulator
from dangosim.randomness import SeedMode


ProgressCallback = Callable[[int, int], None]
CancelRequested = Callable[[], bool]


@dataclass(frozen=True)
class _WorkerRaceConfig:
    track_length: int
    track_finish: int
    track_midpoint: int | float
    devices: tuple[tuple[int, str], ...]
    dangos: tuple[DangoConfig, ...]
    boss_ranked: bool


@dataclass(frozen=True)
class _ChunkRequest:
    config: _WorkerRaceConfig
    start_index: int
    runs: int
    base_seed: int


@dataclass(frozen=True)
class _ChunkResult:
    completed_runs: int
    wins: dict[str, int]
    rank_totals: dict[str, int]


def resolve_worker_count(workers: int | str | None, *, runs: int) -> int:
    cpu_count = _available_worker_count()
    if workers is None or workers == "auto":
        requested = _automatic_worker_count(cpu_count)
    elif workers == "full":
        requested = cpu_count
    elif isinstance(workers, str):
        try:
            requested = int(workers)
        except ValueError as exc:
            raise ValueError("--workers must be 'auto', 'full', or a positive integer.") from exc
    else:
        requested = workers

    if requested < 1:
        raise ValueError("--workers must be at least 1.")
    return min(requested, cpu_count, max(1, runs))


def _available_worker_count() -> int:
    return max(1, os.cpu_count() or 1)


def _automatic_worker_count(cpu_count: int) -> int:
    return max(1, (cpu_count * 2) // 3)


def simulate_many(
    config: RaceConfig,
    *,
    runs: int,
    seed: int | None,
    seed_mode: SeedMode = SeedMode.FIXED,
    progress_callback: ProgressCallback | None = None,
    cancel_requested: CancelRequested | None = None,
    workers: int | str | None = 1,
    chunk_size: int | None = None,
) -> dict[str, object]:
    effective_workers = resolve_worker_count(workers, runs=runs)
    effective_chunk_size = _resolve_chunk_size(chunk_size, runs=runs, workers=effective_workers)
    if effective_workers == 1:
        return _simulate_many_sequential(
            config,
            runs=runs,
            seed=seed,
            seed_mode=seed_mode,
            progress_callback=progress_callback,
            cancel_requested=cancel_requested,
        )
    return _simulate_many_parallel(
        config,
        runs=runs,
        seed=seed,
        seed_mode=seed_mode,
        progress_callback=progress_callback,
        cancel_requested=cancel_requested,
        workers=effective_workers,
        chunk_size=effective_chunk_size,
    )


def _simulate_many_sequential(
    config: RaceConfig,
    *,
    runs: int,
    seed: int | None,
    seed_mode: SeedMode,
    progress_callback: ProgressCallback | None,
    cancel_requested: CancelRequested | None,
) -> dict[str, object]:
    dango_names = {dango.id: dango.name for dango in config.dangos}
    ranked_ids = _ranked_ids(config)
    wins = {dango_id: 0 for dango_id in ranked_ids}
    rank_totals = {dango_id: 0 for dango_id in ranked_ids}

    completed_runs = 0
    for index in range(runs):
        if cancel_requested is not None and cancel_requested():
            break
        run_seed = _base_seed(config, seed) + index
        snapshot = RaceSimulator(replace(config, seed=run_seed)).run_until_finished()
        _aggregate_rankings(snapshot.rankings, ranked_ids=ranked_ids, wins=wins, rank_totals=rank_totals)
        completed_runs += 1
        if progress_callback is not None:
            progress_callback(completed_runs, runs)

    return _summary(
        ranked_ids=ranked_ids,
        dango_names=dango_names,
        wins=wins,
        rank_totals=rank_totals,
        runs=runs,
        completed_runs=completed_runs,
        seed=seed,
        seed_mode=seed_mode,
    )


def _simulate_many_parallel(
    config: RaceConfig,
    *,
    runs: int,
    seed: int | None,
    seed_mode: SeedMode,
    progress_callback: ProgressCallback | None,
    cancel_requested: CancelRequested | None,
    workers: int,
    chunk_size: int,
) -> dict[str, object]:
    dango_names = {dango.id: dango.name for dango in config.dangos}
    ranked_ids = _ranked_ids(config)
    wins = {dango_id: 0 for dango_id in ranked_ids}
    rank_totals = {dango_id: 0 for dango_id in ranked_ids}
    worker_config = _pack_config(config)
    run_seed_base = _base_seed(config, seed)

    completed_runs = 0
    next_index = 0
    cancelled = False
    futures: dict[Future[_ChunkResult], None] = {}

    with ProcessPoolExecutor(max_workers=workers) as executor:
        for _ in range(workers):
            if not _schedule_next_chunk(
                executor,
                futures=futures,
                worker_config=worker_config,
                next_index=next_index,
                total_runs=runs,
                chunk_size=chunk_size,
                base_seed=run_seed_base,
                cancel_requested=cancel_requested,
            ):
                cancelled = cancel_requested is not None and cancel_requested()
                break
            next_index += min(chunk_size, runs - next_index)

        while futures:
            future = next(as_completed(futures))
            futures.pop(future)
            chunk = future.result()
            completed_runs += chunk.completed_runs
            _merge_counts(wins, chunk.wins)
            _merge_counts(rank_totals, chunk.rank_totals)
            if progress_callback is not None:
                progress_callback(completed_runs, runs)

            if cancel_requested is not None and cancel_requested():
                cancelled = True

            if not cancelled and next_index < runs:
                scheduled_runs = min(chunk_size, runs - next_index)
                future = executor.submit(
                    _run_chunk,
                    _ChunkRequest(
                        config=worker_config,
                        start_index=next_index,
                        runs=scheduled_runs,
                        base_seed=run_seed_base,
                    ),
                )
                futures[future] = None
                next_index += scheduled_runs

    return _summary(
        ranked_ids=ranked_ids,
        dango_names=dango_names,
        wins=wins,
        rank_totals=rank_totals,
        runs=runs,
        completed_runs=completed_runs,
        seed=seed,
        seed_mode=seed_mode,
    )


def _run_chunk(request: _ChunkRequest) -> _ChunkResult:
    config = _unpack_config(request.config, seed=None)
    ranked_ids = _ranked_ids(config)
    wins = {dango_id: 0 for dango_id in ranked_ids}
    rank_totals = {dango_id: 0 for dango_id in ranked_ids}

    for offset in range(request.runs):
        run_seed = request.base_seed + request.start_index + offset
        snapshot = RaceSimulator(replace(config, seed=run_seed)).run_until_finished()
        _aggregate_rankings(snapshot.rankings, ranked_ids=ranked_ids, wins=wins, rank_totals=rank_totals)

    return _ChunkResult(completed_runs=request.runs, wins=wins, rank_totals=rank_totals)


def _schedule_next_chunk(
    executor: ProcessPoolExecutor,
    *,
    futures: dict[Future[_ChunkResult], None],
    worker_config: _WorkerRaceConfig,
    next_index: int,
    total_runs: int,
    chunk_size: int,
    base_seed: int,
    cancel_requested: CancelRequested | None,
) -> bool:
    if next_index >= total_runs:
        return False
    if cancel_requested is not None and cancel_requested():
        return False
    scheduled_runs = min(chunk_size, total_runs - next_index)
    futures[
        executor.submit(
            _run_chunk,
            _ChunkRequest(
                config=worker_config,
                start_index=next_index,
                runs=scheduled_runs,
                base_seed=base_seed,
            ),
        )
    ] = None
    return True


def _pack_config(config: RaceConfig) -> _WorkerRaceConfig:
    return _WorkerRaceConfig(
        track_length=config.track.length,
        track_finish=config.track.finish,
        track_midpoint=config.track.midpoint,
        devices=tuple(sorted((position, device.value) for position, device in config.track.devices.items())),
        dangos=tuple(config.dangos),
        boss_ranked=config.boss_ranked,
    )


def _unpack_config(config: _WorkerRaceConfig, *, seed: int | None) -> RaceConfig:
    track = TrackConfig(
        length=config.track_length,
        finish=config.track_finish,
        devices={position: DeviceType(device) for position, device in config.devices},
        midpoint=config.track_midpoint,
    )
    return RaceConfig(track=track, dangos=list(config.dangos), seed=seed, boss_ranked=config.boss_ranked)


def _resolve_chunk_size(chunk_size: int | None, *, runs: int, workers: int) -> int:
    if chunk_size is not None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1.")
        return chunk_size
    if runs <= 0:
        return 1
    return max(1, min(500, math.ceil(runs / max(1, workers * 16))))


def _base_seed(config: RaceConfig, seed: int | None) -> int:
    return seed if seed is not None else config.seed or 0


def _ranked_ids(config: RaceConfig) -> list[str]:
    return [
        dango.id
        for dango in config.dangos
        if (config.boss_ranked if dango.is_boss else dango.ranked)
    ]


def _aggregate_rankings(
    rankings: tuple[str, ...],
    *,
    ranked_ids: list[str],
    wins: dict[str, int],
    rank_totals: dict[str, int],
) -> None:
    if rankings:
        wins[rankings[0]] += 1
    seen: set[str] = set()
    for rank_index, dango_id in enumerate(rankings, start=1):
        if dango_id not in rank_totals:
            continue
        rank_totals[dango_id] += rank_index
        seen.add(dango_id)
    next_rank = len(seen) + 1
    for dango_id in ranked_ids:
        if dango_id not in seen:
            rank_totals[dango_id] += next_rank
            next_rank += 1


def _merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for dango_id, value in source.items():
        target[dango_id] += value


def _summary(
    *,
    ranked_ids: list[str],
    dango_names: dict[str, str],
    wins: dict[str, int],
    rank_totals: dict[str, int],
    runs: int,
    completed_runs: int,
    seed: int | None,
    seed_mode: SeedMode,
) -> dict[str, object]:
    results = []
    denominator = max(1, completed_runs)
    for dango_id in ranked_ids:
        results.append(
            {
                "dango_id": dango_id,
                "name": dango_names[dango_id],
                "wins": wins[dango_id],
                "win_rate": wins[dango_id] / denominator,
                "average_rank": rank_totals[dango_id] / denominator if completed_runs else 0,
            }
        )
    results.sort(key=lambda item: (-float(item["win_rate"]), str(item["dango_id"])))
    return {
        "runs": runs,
        "completed_runs": completed_runs,
        "cancelled": completed_runs < runs,
        "seed_mode": seed_mode.value,
        "base_seed": seed,
        "results": results,
    }
