from __future__ import annotations

import math
import os
from collections.abc import Callable

from dangosim.core.config_loader import load_race_config
from dangosim.core.models import RaceConfig
from dangosim.gui.services import GuiRaceController, run_batch_simulation
from dangosim.gui.view_models import (
    BossMode,
    ParticipantCardState,
    RaceViewState,
    build_participant_cards,
    build_race_config_from_cards,
)
from dangosim.resources import resource_path

APP_TITLE = "DangoSimulator 小團快跑模擬器"


def run() -> int:
    try:
        from PySide6.QtCore import QThread, QTimer, Qt, Signal
        from PySide6.QtGui import QColor, QPainter, QPen
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFrame,
            QGraphicsEllipseItem,
            QGraphicsScene,
            QGraphicsTextItem,
            QGraphicsView,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QListWidget,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QScrollArea,
            QSpinBox,
            QSplitter,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "PySide6 is not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install -r requirements-gui.txt"
        ) from exc

    class TrackScene(QGraphicsScene):
        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setSceneRect(0, 0, 620, 460)

        def render_state(self, config: RaceConfig, state: RaceViewState) -> None:
            self.clear()
            cx, cy = 310, 225
            rx, ry = 245, 165
            length = config.track.length
            pen = QPen(QColor("#55708a"), 2)
            self.addEllipse(cx - rx, cy - ry, rx * 2, ry * 2, pen)
            points = {}
            for index in range(1, length + 1):
                angle = (index - 1) / length * math.tau
                x = cx + math.cos(angle) * rx
                y = cy + math.sin(angle) * ry
                points[index] = (x, y)
                device = state.devices.get(index, "")
                color = {
                    "advance": "#65c56f",
                    "block": "#e37272",
                    "time_rift": "#9270d8",
                }.get(device, "#d8e1ea")
                item = self.addEllipse(x - 9, y - 9, 18, 18, QPen(QColor("#6a7783"), 1), QColor(color))
                item.setToolTip(f"格 {index} {device or '空白'}")
                if index == config.track.finish:
                    self.addText("終").setPos(x - 11, y - 34)

            palette = ["#5da5da", "#60bd68", "#f17cb0", "#b2912f", "#b276b2", "#decf3f", "#7e62c9"]
            for dango_index, (dango_id, position) in enumerate(state.positions.items()):
                x, y = points.get(position, points[1])
                stack = state.stacks.get(position, [])
                stack_index = stack.index(dango_id) if dango_id in stack else 0
                offset_y = -stack_index * 17
                color = palette[dango_index % len(palette)]
                if dango_id == "boss":
                    color = "#7e62c9"
                piece = QGraphicsEllipseItem(x - 15, y - 28 + offset_y, 30, 30)
                piece.setBrush(QColor(color))
                piece.setPen(QPen(QColor("#2f3a44"), 2))
                self.addItem(piece)
                label = QGraphicsTextItem(dango_id[:2])
                label.setDefaultTextColor(QColor("#101820"))
                label.setPos(x - 12, y - 26 + offset_y)
                self.addItem(label)

    class ParticipantCard(QFrame):
        def __init__(self, state: ParticipantCardState, on_change: Callable[[], None]) -> None:
            super().__init__()
            self.state = state
            self.on_change = on_change
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.setStyleSheet("QFrame { border-radius: 6px; padding: 6px; }")
            layout = QVBoxLayout(self)
            header = QHBoxLayout()
            self.checkbox = QCheckBox(state.name)
            self.checkbox.setChecked(state.selected)
            self.checkbox.setEnabled(not state.is_boss)
            header.addWidget(self.checkbox)
            header.addWidget(QLabel(state.group))
            layout.addLayout(header)
            note = QLabel(state.skill_note)
            note.setWordWrap(True)
            layout.addWidget(note)
            self.mode = QComboBox()
            self.mode.addItem("干擾者", BossMode.DISRUPTOR.value)
            self.mode.addItem("參賽者", BossMode.RANKED.value)
            self.mode.setVisible(state.is_boss)
            self.mode.setCurrentIndex(1 if state.boss_mode is BossMode.RANKED else 0)
            layout.addWidget(self.mode)
            self.checkbox.stateChanged.connect(self._changed)
            self.mode.currentIndexChanged.connect(self._changed)

        def _changed(self) -> None:
            mode = BossMode(self.mode.currentData()) if self.state.is_boss else BossMode.NONE
            self.state = self.state.with_updates(selected=self.checkbox.isChecked(), boss_mode=mode)
            self.on_change()

    class SimulationWorker(QThread):
        finished_with_rows = Signal(list)
        failed = Signal(str)

        def __init__(self, config: RaceConfig, runs: int, seed: int | None) -> None:
            super().__init__()
            self.config = config
            self.runs = runs
            self.seed = seed

        def run(self) -> None:
            try:
                self.finished_with_rows.emit(run_batch_simulation(self.config, runs=self.runs, seed=self.seed))
            except Exception as exc:  # GUI boundary: surface unexpected worker errors to the user.
                self.failed.emit(str(exc))

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(APP_TITLE)
            self.config_path = resource_path("data/default_race.json")
            self.base_config = load_race_config(self.config_path.read_text(encoding="utf-8"))
            self.active_config = self.base_config
            self.cards = build_participant_cards(self.base_config)
            self.card_widgets: list[ParticipantCard] = []
            self.controller: GuiRaceController | None = None
            self.worker: SimulationWorker | None = None

            self.auto_timer = QTimer(self)
            self.auto_timer.timeout.connect(self.step_race)

            root = QWidget()
            root_layout = QVBoxLayout(root)
            title = QLabel(APP_TITLE)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet("font-size: 22px; font-weight: 700;")
            root_layout.addWidget(title)

            main_splitter = QSplitter(Qt.Orientation.Horizontal)
            main_splitter.addWidget(self._build_left_panel())
            main_splitter.addWidget(self._build_center_panel())
            main_splitter.addWidget(self._build_right_panel())
            main_splitter.setSizes([280, 650, 280])
            root_layout.addWidget(main_splitter, 1)
            root_layout.addWidget(self._build_results_panel())
            self.setCentralWidget(root)

            self.refresh_selected_summary()
            self.reset_race()

        def _build_left_panel(self) -> QWidget:
            panel = QWidget()
            layout = QVBoxLayout(panel)
            layout.addWidget(QLabel("參賽團子"))
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            body = QWidget()
            body_layout = QVBoxLayout(body)
            for card in self.cards:
                widget = ParticipantCard(card, self._sync_cards_from_widgets)
                self.card_widgets.append(widget)
                body_layout.addWidget(widget)
            body_layout.addStretch()
            scroll.setWidget(body)
            layout.addWidget(scroll, 1)
            self.selected_summary = QLabel()
            self.selected_summary.setWordWrap(True)
            layout.addWidget(self.selected_summary)
            return panel

        def _build_center_panel(self) -> QWidget:
            panel = QWidget()
            layout = QVBoxLayout(panel)
            self.track_scene = TrackScene(panel)
            view = QGraphicsView(self.track_scene)
            view.setRenderHint(QPainter.RenderHint.Antialiasing)
            layout.addWidget(view, 1)

            controls = QHBoxLayout()
            self.start_button = QPushButton("開始")
            self.step_button = QPushButton("下一步")
            self.auto_button = QPushButton("自動播放")
            self.pause_button = QPushButton("暫停")
            self.reset_button = QPushButton("重置")
            self.speed = QSpinBox()
            self.speed.setRange(150, 2000)
            self.speed.setValue(700)
            self.speed.setSuffix(" ms")
            for button in [self.start_button, self.step_button, self.auto_button, self.pause_button, self.reset_button]:
                controls.addWidget(button)
            controls.addWidget(QLabel("速度"))
            controls.addWidget(self.speed)
            layout.addLayout(controls)

            self.dice_label = QLabel("骰子：-")
            self.dice_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.dice_label)

            self.start_button.clicked.connect(self.reset_race)
            self.step_button.clicked.connect(self.step_race)
            self.auto_button.clicked.connect(self.start_auto)
            self.pause_button.clicked.connect(self.pause_auto)
            self.reset_button.clicked.connect(self.reset_race)
            return panel

        def _build_right_panel(self) -> QWidget:
            panel = QWidget()
            layout = QVBoxLayout(panel)
            self.ranking = QListWidget()
            self.events = QListWidget()
            layout.addWidget(QLabel("即時名次"))
            layout.addWidget(self.ranking)
            layout.addWidget(QLabel("事件紀錄"))
            layout.addWidget(self.events, 1)
            return panel

        def _build_results_panel(self) -> QWidget:
            box = QGroupBox("多輪模擬")
            layout = QVBoxLayout(box)
            controls = QHBoxLayout()
            self.run_count = QSpinBox()
            self.run_count.setRange(1, 100_000)
            self.run_count.setValue(1000)
            self.sort_mode = QComboBox()
            self.sort_mode.addItems(["綜合分數", "勝率", "平均名次"])
            self.run_batch_button = QPushButton("執行多輪模擬")
            controls.addWidget(QLabel("場數"))
            controls.addWidget(self.run_count)
            controls.addWidget(QLabel("排序"))
            controls.addWidget(self.sort_mode)
            controls.addWidget(self.run_batch_button)
            controls.addStretch()
            layout.addLayout(controls)

            self.results = QTableWidget(0, 6)
            self.results.setHorizontalHeaderLabels(["排名", "團子", "勝場", "勝率", "平均名次", "綜合分數"])
            layout.addWidget(self.results)
            self.run_batch_button.clicked.connect(self.run_batch)
            return box

        def _sync_cards_from_widgets(self) -> None:
            self.cards = [widget.state for widget in self.card_widgets]
            self.refresh_selected_summary()

        def selected_config(self) -> RaceConfig:
            return build_race_config_from_cards(self.base_config, self.cards)

        def refresh_selected_summary(self) -> None:
            selected = [card.name for card in self.cards if card.selected and not card.is_boss]
            self.selected_summary.setText(f"已選 {len(selected)} 顆：{'、'.join(selected) or '尚未選擇'}")

        def reset_race(self) -> None:
            try:
                self.active_config = self.selected_config()
                self.controller = GuiRaceController(self.active_config)
            except ValueError as exc:
                QMessageBox.warning(self, "設定錯誤", str(exc))
                return
            self.pause_auto()
            self.render_state(self.controller.view_state())

        def step_race(self) -> None:
            if self.controller is None:
                self.reset_race()
                return
            state = self.controller.step()
            self.render_state(state)
            if state.finished:
                self.pause_auto()

        def start_auto(self) -> None:
            self.auto_timer.start(self.speed.value())

        def pause_auto(self) -> None:
            self.auto_timer.stop()

        def render_state(self, state: RaceViewState) -> None:
            self.track_scene.render_state(self.active_config, state)
            self.dice_label.setText(
                f"行動：{state.current_actor or '-'}　骰子：{state.last_roll if state.last_roll is not None else '-'}"
            )
            self.ranking.clear()
            for index, dango_id in enumerate(state.rankings, start=1):
                self.ranking.addItem(f"#{index} {dango_id}")
            unfinished = [dango_id for dango_id in state.positions if dango_id not in state.rankings]
            for dango_id in unfinished:
                self.ranking.addItem(f"賽中 {dango_id}｜{state.positions[dango_id]} 格")
            self.events.clear()
            for message in state.event_log[-80:]:
                self.events.addItem(message)

        def run_batch(self) -> None:
            try:
                config = self.selected_config()
            except ValueError as exc:
                QMessageBox.warning(self, "設定錯誤", str(exc))
                return
            self.run_batch_button.setEnabled(False)
            self.worker = SimulationWorker(config, self.run_count.value(), 20260517)
            self.worker.finished_with_rows.connect(self.render_results)
            self.worker.failed.connect(self.show_worker_error)
            self.worker.start()

        def render_results(self, rows: list) -> None:
            mode = self.sort_mode.currentText()
            if mode == "勝率":
                rows = sorted(rows, key=lambda row: (-row.win_rate, row.average_rank))
            elif mode == "平均名次":
                rows = sorted(rows, key=lambda row: (row.average_rank, -row.win_rate))
            self.results.setRowCount(len(rows))
            for visual_rank, row in enumerate(rows, start=1):
                values = [
                    str(visual_rank),
                    row.name,
                    str(row.wins),
                    f"{row.win_rate:.2%}",
                    f"{row.average_rank:.2f}",
                    f"{row.weighted_score:.4f}",
                ]
                for column, value in enumerate(values):
                    self.results.setItem(visual_rank - 1, column, QTableWidgetItem(value))
            self.run_batch_button.setEnabled(True)

        def show_worker_error(self, message: str) -> None:
            self.run_batch_button.setEnabled(True)
            QMessageBox.warning(self, "模擬失敗", message)

    app = QApplication([])
    window = MainWindow()
    window.resize(1280, 820)
    window.show()
    if os.environ.get("DANGOSIM_GUI_SMOKE") == "1":
        QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
