from __future__ import annotations

import json
from dataclasses import replace

from dangosim.cli.main import simulate_many
from dangosim.core.config_loader import load_race_config
from dangosim.core.simulator import RaceSimulator
from dangosim.resources import resource_path

APP_TITLE = "DangoSimulator 小團快跑模擬器"


def run() -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QPushButton,
            QPlainTextEdit,
            QSpinBox,
            QVBoxLayout,
            QWidget,
        )
    except ModuleNotFoundError as exc:
        raise SystemExit("PySide6 is not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install -r requirements-gui.txt") from exc

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(APP_TITLE)
            self.config_path = resource_path("data/default_race.json")
            self.config = load_race_config(self.config_path.read_text(encoding="utf-8"))

            root = QWidget()
            layout = QVBoxLayout(root)

            title = QLabel(APP_TITLE)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title)

            controls = QHBoxLayout()
            self.run_count = QSpinBox()
            self.run_count.setRange(1, 100_000)
            self.run_count.setValue(1000)
            controls.addWidget(QLabel("批次模擬場數"))
            controls.addWidget(self.run_count)

            single_button = QPushButton("跑單場")
            batch_button = QPushButton("計算勝率")
            controls.addWidget(single_button)
            controls.addWidget(batch_button)
            layout.addLayout(controls)

            self.output = QPlainTextEdit()
            self.output.setReadOnly(True)
            layout.addWidget(self.output)
            self.setCentralWidget(root)

            single_button.clicked.connect(self.run_single_race)
            batch_button.clicked.connect(self.run_batch)
            self.output.setPlainText(f"已載入：{self.config_path}\n參賽團子：{len(self.config.dangos)}")

        def run_single_race(self) -> None:
            snapshot = RaceSimulator(self.config).run_until_finished()
            self.output.setPlainText(
                "單場結果\n"
                + "\n".join(f"{index + 1}. {dango_id}" for index, dango_id in enumerate(snapshot.rankings))
            )

        def run_batch(self) -> None:
            summary = simulate_many(replace(self.config, seed=20260517), runs=self.run_count.value(), seed=20260517)
            self.output.setPlainText(json.dumps(summary, ensure_ascii=False, indent=2))

    app = QApplication([])
    window = MainWindow()
    window.resize(920, 640)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
