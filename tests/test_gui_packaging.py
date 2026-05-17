from __future__ import annotations

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


def test_gui_dashboard_can_create_window_offscreen() -> None:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANGOSIM_GUI_SMOKE"] = "1"

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
