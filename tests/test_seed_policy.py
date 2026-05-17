from __future__ import annotations

import json
from pathlib import Path

import pytest

from dangosim.cli.main import main, simulate_many
from dangosim.core.config_loader import load_race_config
from dangosim.randomness import SeedMode, resolve_seed


def _default_config():
    return load_race_config(Path("data/default_race.json").read_text(encoding="utf-8"))


def test_resolve_seed_uses_fixed_seed_when_provided() -> None:
    resolved = resolve_seed(mode=SeedMode.FIXED, requested_seed=123, config_seed=999)

    assert resolved.mode == SeedMode.FIXED
    assert resolved.seed == 123


def test_resolve_seed_uses_system_random_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    values = iter([111, 222])

    def fake_randbits(bits: int) -> int:
        assert bits == 64
        return next(values)

    monkeypatch.setattr("dangosim.randomness.secrets.randbits", fake_randbits)

    first = resolve_seed(mode=SeedMode.SYSTEM, requested_seed=None, config_seed=999)
    second = resolve_seed(mode=SeedMode.SYSTEM, requested_seed=None, config_seed=999)

    assert first.mode == SeedMode.SYSTEM
    assert first.seed == 111
    assert second.seed == 222


def test_resolve_seed_rejects_invalid_fixed_seed() -> None:
    with pytest.raises(ValueError, match="seed must be between"):
        resolve_seed(mode=SeedMode.FIXED, requested_seed=-1, config_seed=None)


def test_simulate_many_reports_seed_metadata() -> None:
    summary = simulate_many(_default_config(), runs=1, seed=456, seed_mode=SeedMode.FIXED)

    assert summary["seed_mode"] == "fixed"
    assert summary["base_seed"] == 456


def test_cli_system_seed_outputs_actual_seed(tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"

    exit_code = main(
        [
            "simulate",
            "--config",
            "data/default_race.json",
            "--runs",
            "1",
            "--seed-mode",
            "system",
            "--out",
            str(output_path),
            "--format",
            "json",
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["seed_mode"] == "system"
    assert isinstance(payload["base_seed"], int)
