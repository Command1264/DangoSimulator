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
    assert config.track.midpoint == 15
    assert len(config.dangos) >= 6
    assert any(dango.is_boss for dango in config.dangos)


def test_default_race_json_orders_dangos_like_rules_and_names_abilities() -> None:
    config = load_race_config(Path("data/default_race.json").read_text(encoding="utf-8"))

    assert [dango.name for dango in config.dangos if not dango.is_boss] == [
        "陸・赫斯團子",
        "西格莉卡團子",
        "達妮亞團子",
        "緋雪團子",
        "卡提希婭團子",
        "菲比團子",
        "千咲團子",
        "莫寧團子",
        "琳奈團子",
        "愛彌斯團子",
        "守岸人團子",
        "珂萊塔團子",
        "奧古斯塔團子",
        "尤諾團子",
        "弗洛洛團子",
        "長離團子",
        "今汐團子",
        "卡卡羅團子",
    ]
    assert all(ability.name for dango in config.dangos for ability in dango.abilities)


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
    assert payload["seed_mode"] == "fixed"
    assert payload["base_seed"] == 123
    assert sum(item["wins"] for item in payload["results"]) == 5
    assert {item["dango_id"] for item in payload["results"]} == {"lu", "west", "daphne", "snow", "kat", "fei"}


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
    assert {"seed_mode", "base_seed", "dango_id", "name", "wins", "win_rate", "average_rank"}.issubset(rows[0])
    assert rows[0]["seed_mode"] == "fixed"
    assert rows[0]["base_seed"] == "123"
