from __future__ import annotations

import csv
import json
from pathlib import Path

from dangosim.cli.main import main
from dangosim.core.config_loader import load_race_config


def test_default_race_json_is_loadable() -> None:
    default_path = Path("data/default_race.json")

    config = load_race_config(default_path.read_text(encoding="utf-8"))

    assert config.track.length == 32
    assert len(config.dangos) >= 6
    assert any(dango.is_boss for dango in config.dangos)


def test_cli_simulate_writes_json_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"

    exit_code = main(
        [
            "simulate",
            "--config",
            "data/default_race.json",
            "--runs",
            "5",
            "--seed",
            "123",
            "--out",
            str(output_path),
            "--format",
            "json",
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["runs"] == 5
    assert sum(item["wins"] for item in payload["results"]) == 5


def test_cli_simulate_writes_csv_summary(tmp_path: Path) -> None:
    output_path = tmp_path / "result.csv"

    exit_code = main(
        [
            "simulate",
            "--config",
            "data/default_race.json",
            "--runs",
            "3",
            "--seed",
            "123",
            "--out",
            str(output_path),
            "--format",
            "csv",
        ]
    )

    rows = list(csv.DictReader(output_path.open("r", encoding="utf-8", newline="")))
    assert exit_code == 0
    assert rows
    assert {"dango_id", "name", "wins", "win_rate", "average_rank"}.issubset(rows[0])
