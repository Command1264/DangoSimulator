from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from dangosim.gui.app import APP_TITLE
from dangosim.resources import resource_path


def test_gui_module_imports_without_pyside6_runtime_dependency() -> None:
    assert APP_TITLE == "DangoSimulator 小團快跑模擬器"


def test_resource_path_finds_default_data() -> None:
    assert resource_path("data/default_race.json").exists()


def test_pyinstaller_spec_includes_data_directory() -> None:
    spec = Path("DangoSimulator.spec")
    content = spec.read_text(encoding="utf-8")

    assert "data" in content
    assert "dangosim.gui.app" in content


def test_gui_dashboard_can_create_window_offscreen(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANGOSIM_GUI_SMOKE"] = "1"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "version": 1,
                "participants": {},
                "single_race": {"auto_play": True},
                "batch_simulation": {
                    "runs": 1000,
                    "seed_mode": "fixed",
                    "seed": "99",
                    "sort_mode": "綜合分數",
                    "workers": "1",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    env["DANGOSIM_SETTINGS_PATH"] = str(settings_path)

    result = subprocess.run(
        [sys.executable, "-m", "dangosim.gui.app"],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert settings_path.exists()
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved["single_race"]["auto_play"] is True
    assert saved["batch_simulation"]["workers"] == "1"


def test_gui_dashboard_layout_places_events_under_participants_and_aligns_tables(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANGOSIM_GUI_LAYOUT_PROBE"] = "1"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "version": 1,
                "participants": {},
                "single_race": {"auto_play": False},
                "batch_simulation": {
                    "runs": 1000,
                    "seed_mode": "fixed",
                    "seed": "99",
                    "sort_mode": "綜合分數",
                    "workers": "1",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    env["DANGOSIM_SETTINGS_PATH"] = str(settings_path)

    result = subprocess.run(
        [sys.executable, "-m", "dangosim.gui.app"],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    probe = json.loads(result.stdout)
    assert probe["event_log_parent"] == "left_panel"
    assert probe["splitter_widgets"] == ["left_panel", "center_panel", "right_panel"]
    assert probe["ranking_alignment"] == ["center", "left", "right", "center"]
    assert probe["round_action_alignment"] == ["center", "left", "center", "center"]
    assert probe["result_alignment"] == ["center", "left", "right", "right", "right", "right"]


def test_gui_event_log_auto_scrolls_only_when_already_at_bottom(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANGOSIM_GUI_EVENT_SCROLL_PROBE"] = "1"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "version": 1,
                "participants": {},
                "single_race": {"auto_play": False},
                "batch_simulation": {
                    "runs": 1000,
                    "seed_mode": "fixed",
                    "seed": "99",
                    "sort_mode": "綜合分數",
                    "workers": "1",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    env["DANGOSIM_SETTINGS_PATH"] = str(settings_path)

    result = subprocess.run(
        [sys.executable, "-m", "dangosim.gui.app"],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    probe = json.loads(result.stdout)
    assert probe["no_scroll_auto_bottom"] is True
    assert probe["bottom_auto_bottom"] is True
    assert probe["review_position_preserved"] is True
