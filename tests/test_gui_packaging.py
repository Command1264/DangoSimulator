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
    assert probe["window_maximized"] is True
    assert probe["workspace_nav_items"] == ["單輪模擬", "多輪模擬", "設定"]
    assert probe["workspace_stack_pages"] == [
        "single_race_workspace",
        "batch_simulation_workspace",
        "settings_workspace",
    ]
    assert probe["active_workspace"] == "single_race_workspace"
    assert probe["title_parent"] == "center_panel"
    assert probe["event_log_parent"] == "left_panel"
    assert probe["splitter_widgets"] == ["left_panel", "center_panel", "right_panel"]
    assert probe["result_table_parent"] == "batch_simulation_workspace"
    assert "settings_workspace" in probe["seed_mode_ancestors"]
    assert "settings_workspace" in probe["seed_input_ancestors"]
    assert "Seed 設定" in probe["settings_workspace_labels"]
    assert "固定 Seed：" in probe["settings_workspace_labels"]
    assert "Seed" not in probe["batch_workspace_labels"]
    assert "固定 Seed：" not in probe["batch_workspace_labels"]
    assert "settings_workspace" in probe["participant_setup_button_ancestors"]
    assert "參賽團子" not in probe["left_panel_labels"]
    assert probe["ranking_alignment"] == ["center", "left", "right", "center"]
    assert probe["round_action_alignment"] == ["center", "left", "center", "center"]
    assert probe["result_alignment"] == ["center", "left", "right", "right", "right", "right"]
    assert probe["result_visible_rows"] >= 7


def test_gui_control_state_locks_global_settings_and_restarts_after_finish(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANGOSIM_GUI_CONTROL_STATE_PROBE"] = "1"
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
    assert probe["initial"] == {
        "start": True,
        "participant_setup": True,
        "seed_mode": True,
        "seed_input": True,
    }
    assert probe["during_single"] == {
        "start": False,
        "participant_setup": False,
        "seed_mode": False,
        "seed_input": False,
    }
    assert probe["after_finish"]["start"] is True
    assert probe["after_finish"]["participant_setup"] is True
    assert probe["after_finish"]["seed_mode"] is True
    assert probe["after_finish"]["seed_input"] is True
    assert probe["after_finish"]["single_race_active"] is False
    assert probe["finished_in_steps"] > 0


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


def test_gui_system_seed_preserves_fixed_seed_input(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANGOSIM_GUI_SYSTEM_SEED_PROBE"] = "1"
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "version": 1,
                "participants": {},
                "single_race": {"auto_play": False},
                "batch_simulation": {
                    "runs": 1000,
                    "seed_mode": "system",
                    "seed": "12345",
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
    assert probe["fixed_seed_label"] == "固定 Seed："
    assert probe["fixed_seed_after_single_race_config"] == "12345"
    assert probe["fixed_seed_after_system_batch_result"] == "12345"
    assert probe["current_seed_after_system_batch_result"] == 987654
    assert probe["seed_label_after_system_batch_result"] == "目前 seed：987654（system）"
