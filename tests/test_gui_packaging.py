from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from dangosim import __version__
from dangosim.gui.app import APP_AUTHOR, APP_TITLE
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
    assert probe["workspace_nav_widget_class"] == "QTabBar"
    assert probe["workspace_shell_layout"] == "vertical"
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
    assert f"作者：{APP_AUTHOR}" in probe["settings_workspace_labels"]
    assert f"版本：{__version__}" in probe["settings_workspace_labels"]
    assert "單輪模擬設定" not in probe["settings_workspace_labels"]
    assert "多輪模擬設定" not in probe["settings_workspace_labels"]
    assert "Seed" not in probe["batch_workspace_labels"]
    assert "固定 Seed：" not in probe["batch_workspace_labels"]
    assert "settings_workspace" in probe["participant_setup_button_ancestors"]
    assert "參賽團子" not in probe["left_panel_labels"]
    assert probe["ranking_alignment"] == ["center", "left", "center", "center"]
    assert probe["round_action_alignment"] == ["center", "left", "center", "center"]
    assert probe["result_alignment"] == ["center", "left", "right", "right", "right", "right"]
    assert probe["result_visible_rows"] >= 7
    assert all(abs(offset) <= 1 for offset in probe["single_map_center_offsets"])
    assert all(widths["left"] == widths["right"] for widths in probe["single_info_panel_widths"])
    assert all(widths["left"] >= 400 and widths["right"] >= 400 for widths in probe["single_info_panel_widths"])
    assert probe["ranking_word_wrap"] is False
    assert probe["round_action_word_wrap"] is False
    assert probe["ranking_section_widths"][0] <= 52
    assert probe["ranking_section_widths"][1] >= 160
    assert probe["ranking_section_widths"][2] <= 52
    assert probe["round_action_section_widths"][0] <= 52
    assert probe["round_action_section_widths"][1] >= 160
    assert probe["round_action_section_widths"][2] <= 52
    assert probe["readonly_views"] == {
        "event_log": True,
        "ranking": True,
        "round_action": True,
        "results": True,
    }
    assert probe["single_status_table_selection"] == {
        "ranking": {
            "behavior": "SelectRows",
            "mode": "SingleSelection",
            "delegate": "LeadingSelectionDelegate",
        },
        "round_action": {
            "behavior": "SelectRows",
            "mode": "SingleSelection",
            "delegate": "LeadingSelectionDelegate",
        },
    }


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
        "step": False,
        "auto_play": True,
        "pause": False,
        "reset": False,
        "run_batch": True,
        "run_count": True,
        "worker_count": True,
        "stop_batch": False,
        "participant_setup": True,
        "seed_mode": True,
        "seed_input": True,
    }
    assert probe["during_single"] == {
        "start": False,
        "step": True,
        "auto_play": True,
        "pause": True,
        "reset": True,
        "run_batch": True,
        "run_count": True,
        "worker_count": True,
        "stop_batch": False,
        "participant_setup": False,
        "seed_mode": False,
        "seed_input": False,
    }
    assert probe["during_single_run_batch_attempt"] == {
        "warning_messages": [],
        "question_shown": True,
        "batch_running": False,
    }
    assert probe["during_batch_only"] == {
        "start": True,
        "step": False,
        "auto_play": True,
        "pause": False,
        "reset": False,
        "run_batch": False,
        "run_count": False,
        "worker_count": False,
        "stop_batch": True,
        "participant_setup": False,
        "seed_mode": False,
        "seed_input": False,
    }
    assert probe["both_active"] == {
        "start": False,
        "step": True,
        "auto_play": True,
        "pause": True,
        "reset": True,
        "run_batch": False,
        "run_count": False,
        "worker_count": False,
        "stop_batch": True,
        "participant_setup": False,
        "seed_mode": False,
        "seed_input": False,
        "single_race_active": True,
        "batch_running": True,
    }
    assert probe["seed_label_after_batch_result_while_single_active"] == probe["seed_label_before_batch_result"]
    assert probe["after_single_finish_with_batch"]["start"] is True
    assert probe["after_single_finish_with_batch"]["run_batch"] is False
    assert probe["after_single_finish_with_batch"]["stop_batch"] is True
    assert probe["after_single_finish_with_batch"]["participant_setup"] is False
    assert probe["after_single_finish_with_batch"]["seed_mode"] is False
    assert probe["after_single_finish_with_batch"]["seed_input"] is False
    assert probe["after_single_finish_with_batch"]["single_race_active"] is False
    assert probe["after_single_finish_with_batch"]["batch_running"] is True
    assert probe["after_finish"]["start"] is True
    assert probe["after_finish"]["run_batch"] is True
    assert probe["after_finish"]["participant_setup"] is True
    assert probe["after_finish"]["seed_mode"] is True
    assert probe["after_finish"]["seed_input"] is True
    assert probe["after_finish"]["single_race_active"] is False
    assert probe["after_finish"]["batch_running"] is False
    assert probe["finished_in_steps"] > 0


def test_single_reset_does_not_clear_running_batch_progress(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANGOSIM_GUI_CONCURRENT_RESET_PROBE"] = "1"
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
    assert probe == {
        "single_race_active": False,
        "batch_running": True,
        "progress_value": 3,
        "progress_maximum": 10,
        "progress_format": "3 / 10",
        "eta": "ETA：5 秒",
    }


def test_participant_dialog_wraps_summary_and_equalizes_skill_notes_by_row(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANGOSIM_PARTICIPANT_DIALOG_LAYOUT_PROBE"] = "1"
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
    assert probe["count_label_word_wrap"] is True
    assert probe["count_label_horizontal_policy"] == "Ignored"
    assert probe["count_label_width"] <= probe["dialog_width"]
    assert all(len(set(row_heights)) == 1 for row_heights in probe["skill_note_heights_by_row"])
    assert all(alignment == "center" for alignment in probe["skill_note_alignments"])


def test_batch_results_sort_by_header_with_tri_state_and_rank_direction(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANGOSIM_GUI_RESULT_SORT_PROBE"] = "1"
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
                    "sort_mode": "平均名次",
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
    assert probe["default"] == {
        "headers": ["排名", "團子", "勝場", "勝率", "平均名次", "綜合分數 ▼"],
        "names": ["Alpha", "Gamma", "Beta"],
        "ranks": ["1", "2", "3"],
        "state": {"column": "weighted_score", "direction": "desc"},
    }
    assert probe["win_rate_desc"] == {
        "names": ["Beta", "Gamma", "Alpha"],
        "ranks": ["1", "2", "3"],
        "state": {"column": "win_rate", "direction": "desc"},
    }
    assert probe["win_rate_asc"] == {
        "names": ["Alpha", "Gamma", "Beta"],
        "ranks": ["3", "2", "1"],
        "state": {"column": "win_rate", "direction": "asc"},
    }
    assert probe["win_rate_default"] == {
        "names": ["Alpha", "Gamma", "Beta"],
        "ranks": ["1", "2", "3"],
        "state": {"column": "weighted_score", "direction": "desc"},
    }
    assert probe["after_rank_click"] == probe["win_rate_default"]


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
