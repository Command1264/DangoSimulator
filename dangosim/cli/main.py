from __future__ import annotations

import argparse
import csv
import json
import multiprocessing
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from dangosim.core.batch import simulate_many
from dangosim.core.config_loader import ConfigValidationError, load_race_config
from dangosim.core.models import RaceConfig
from dangosim.randomness import SeedMode, resolve_seed


def main(argv: Sequence[str] | None = None) -> int:
    multiprocessing.freeze_support()
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "simulate":
        return _run_simulate(args)
    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dangosim", description="鳴潮小團快跑模擬器")
    subparsers = parser.add_subparsers(dest="command")

    simulate = subparsers.add_parser("simulate", help="執行 headless 批次模擬")
    simulate.add_argument("--config", required=True, help="Race JSON 設定檔")
    simulate.add_argument("--runs", type=int, default=1000, help="模擬場數")
    simulate.add_argument("--seed", type=int, default=None, help="固定隨機種子")
    simulate.add_argument("--seed-mode", choices=[mode.value for mode in SeedMode], default=SeedMode.FIXED.value, help="seed 模式")
    simulate.add_argument("--workers", default="1", help="平行處理數量，使用 auto 或正整數")
    simulate.add_argument("--out", required=True, help="輸出檔案")
    simulate.add_argument("--format", choices=["json", "csv"], default="json", help="輸出格式")
    return parser


def _run_simulate(args: argparse.Namespace) -> int:
    if args.runs <= 0 or args.runs > 100_000:
        raise SystemExit("--runs must be between 1 and 100000.")

    config_path = Path(args.config)
    try:
        config = load_race_config(config_path.read_text(encoding="utf-8"))
    except (OSError, ConfigValidationError) as exc:
        raise SystemExit(f"Failed to load config: {exc}") from exc

    seed_mode = SeedMode(args.seed_mode)
    try:
        resolved_seed = resolve_seed(mode=seed_mode, requested_seed=args.seed, config_seed=config.seed)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    try:
        summary = simulate_many(
            _default_selected_config(config),
            runs=args.runs,
            seed=resolved_seed.seed,
            seed_mode=resolved_seed.mode,
            workers=args.workers,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        _write_csv(
            output_path,
            summary["results"],  # type: ignore[arg-type]
            seed_mode=str(summary["seed_mode"]),
            base_seed=int(summary["base_seed"]),
        )
    return 0


def _default_selected_config(config: RaceConfig) -> RaceConfig:
    selected = [dango for dango in config.dangos if dango.default_selected or dango.is_boss]
    return replace(config, dangos=selected)


def _write_csv(path: Path, rows: list[dict[str, object]], *, seed_mode: str, base_seed: int) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["seed_mode", "base_seed", "dango_id", "name", "wins", "win_rate", "average_rank"],
        )
        writer.writeheader()
        writer.writerows({"seed_mode": seed_mode, "base_seed": base_seed, **row} for row in rows)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
