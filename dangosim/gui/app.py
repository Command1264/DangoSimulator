from __future__ import annotations

import math
import multiprocessing
import os
import time
from collections.abc import Callable
from dataclasses import replace

from dangosim.core.batch import resolve_worker_count
from dangosim.core.config_loader import load_race_config
from dangosim.core.models import RaceConfig
from dangosim.gui.batch_estimation import (
    build_batch_estimate_confirmation_message,
    estimate_sample_runs,
    estimate_seconds_from_sample,
)
from dangosim.gui.layers import build_piece_layers
from dangosim.gui.services import BatchSimulationResult, GuiRaceController, run_batch_simulation
from dangosim.gui.settings import (
    BatchSimulationSettings,
    MAX_BATCH_RUNS,
    ParticipantSettings,
    SingleRaceSettings,
    UserSettings,
    UserSettingsStore,
    apply_settings_to_cards,
)
from dangosim.gui.view_models import (
    BossMode,
    ParticipantCardState,
    RaceViewState,
    build_participant_cards,
    build_race_config_from_cards,
    format_event_log_message,
    is_auto_play_control_enabled,
    is_seed_input_enabled,
)
from dangosim.randomness import MAX_SEED_EXCLUSIVE, SeedMode, resolve_seed
from dangosim.resources import resource_path

APP_TITLE = "DangoSimulator 小團快跑模擬器"


def run() -> int:
    multiprocessing.freeze_support()
    try:
        from PySide6.QtCore import QThread, QTimer, Qt, Signal
        from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
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
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMessageBox,
            QProgressBar,
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

    piece_palette = [
        "#5da5da",
        "#60bd68",
        "#f17cb0",
        "#b2912f",
        "#b276b2",
        "#decf3f",
        "#7e62c9",
    ]

    def piece_color(dango_id: str, state: RaceViewState) -> str:
        if dango_id == "boss":
            return "#7e62c9"
        dango_ids = list(state.positions)
        index = dango_ids.index(dango_id) if dango_id in state.positions else 0
        return piece_palette[index % len(piece_palette)]

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
            track = self.addEllipse(cx - rx, cy - ry, rx * 2, ry * 2, pen)
            track.setZValue(0)
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
                item.setZValue(10)
                item.setToolTip(f"格 {index} {device or '空白'}")
                if index == config.track.finish:
                    finish_label = self.addText("終")
                    finish_label.setZValue(20)
                    finish_label.setPos(x - 11, y - 34)

            layers = build_piece_layers(positions=state.positions, stacks=state.stacks)
            for dango_id, position in state.positions.items():
                x, y = points.get(position, points[1])
                layer = layers[dango_id]
                offset_y = layer.offset_y
                color = piece_color(dango_id, state)
                shadow = QGraphicsEllipseItem(x - 12, y - 24 + offset_y, 30, 30)
                shadow.setBrush(QColor(16, 24, 32, 55))
                shadow.setPen(QPen(Qt.PenStyle.NoPen))
                shadow.setZValue(layer.shadow_z)
                self.addItem(shadow)
                piece = QGraphicsEllipseItem(x - 15, y - 28 + offset_y, 30, 30)
                piece.setBrush(QColor(color))
                piece.setPen(QPen(QColor("#2f3a44"), 2))
                piece.setZValue(layer.piece_z)
                piece.setToolTip(state.dango_names.get(dango_id, dango_id))
                self.addItem(piece)
                if dango_id == state.current_actor:
                    highlight = QGraphicsEllipseItem(x - 19, y - 32 + offset_y, 38, 38)
                    highlight.setBrush(QColor(0, 0, 0, 0))
                    highlight.setPen(QPen(QColor("#f0c64a"), 3))
                    highlight.setZValue(layer.highlight_z)
                    self.addItem(highlight)
                label = QGraphicsTextItem(state.avatar_labels.get(dango_id, dango_id[:1]))
                label.setDefaultTextColor(QColor("#101820"))
                label.setZValue(layer.label_z)
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
            if state.group:
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

        def set_editing_enabled(self, enabled: bool) -> None:
            self.checkbox.setEnabled(enabled and not self.state.is_boss)
            self.mode.setEnabled(enabled)

    class SimulationWorker(QThread):
        finished_with_result = Signal(object)
        cancelled_with_result = Signal(object)
        failed = Signal(str)
        progress_changed = Signal(int, int, float)

        def __init__(
            self,
            config: RaceConfig,
            runs: int,
            seed: int | None,
            seed_mode: SeedMode,
            workers: int | str | None,
        ) -> None:
            super().__init__()
            self.config = config
            self.runs = runs
            self.seed = seed
            self.seed_mode = seed_mode
            self.workers = workers
            self._cancel_requested = False

        def cancel(self) -> None:
            self._cancel_requested = True

        def run(self) -> None:
            try:
                started_at = time.perf_counter()

                def report_progress(completed: int, total: int) -> None:
                    elapsed = time.perf_counter() - started_at
                    eta_seconds = (elapsed / completed) * (total - completed) if completed else 0.0
                    self.progress_changed.emit(completed, total, eta_seconds)

                result = run_batch_simulation(
                    self.config,
                    runs=self.runs,
                    seed=self.seed,
                    seed_mode=self.seed_mode,
                    progress_callback=report_progress,
                    cancel_requested=lambda: self._cancel_requested,
                    workers=self.workers,
                )
                if result.cancelled:
                    self.cancelled_with_result.emit(result)
                else:
                    self.finished_with_result.emit(result)
            except Exception as exc:  # GUI boundary: surface unexpected worker errors to the user.
                self.failed.emit(str(exc))

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle(APP_TITLE)
            self.config_path = resource_path("data/default_race.json")
            self.base_config = load_race_config(self.config_path.read_text(encoding="utf-8"))
            self.settings_store = UserSettingsStore.default()
            self.user_settings = self.settings_store.load()
            self.loading_settings = True
            self.active_config = self.base_config
            self.cards = apply_settings_to_cards(build_participant_cards(self.base_config), self.user_settings)
            self.card_widgets: list[ParticipantCard] = []
            self.controller: GuiRaceController | None = None
            self.worker: SimulationWorker | None = None
            self.current_seed = self.base_config.seed or 0
            self.single_race_active = False
            self.batch_running = False

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

            self.apply_loaded_settings_to_controls()
            self.refresh_selected_summary()
            self.reset_race()
            self.loading_settings = False
            self.connect_settings_persistence()
            self.persist_user_settings()

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
            self.auto_play = QCheckBox("自動播放")
            self.pause_button = QPushButton("暫停")
            self.reset_button = QPushButton("重置")
            self.speed = QSpinBox()
            self.speed.setRange(150, 2000)
            self.speed.setValue(700)
            self.speed.setSuffix(" ms")
            for button in [self.start_button, self.step_button, self.pause_button, self.reset_button]:
                controls.addWidget(button)
            controls.addWidget(self.auto_play)
            controls.addWidget(QLabel("速度"))
            controls.addWidget(self.speed)
            layout.addLayout(controls)

            self.dice_label = QLabel("骰子：-")
            self.dice_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.dice_label)
            self.seed_label = QLabel(f"目前 seed：{self.current_seed}")
            self.seed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.seed_label)

            self.start_button.clicked.connect(self.start_race)
            self.step_button.clicked.connect(self.step_race)
            self.auto_play.stateChanged.connect(self.handle_auto_play_changed)
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
            self.run_count.setRange(1, MAX_BATCH_RUNS)
            self.run_count.setValue(1000)
            self.run_count.setGroupSeparatorShown(True)
            self.run_count.setMinimumWidth(125)
            self.seed_mode = QComboBox()
            self.seed_mode.addItem("固定 seed", SeedMode.FIXED.value)
            self.seed_mode.addItem("系統隨機 seed", SeedMode.SYSTEM.value)
            self.seed_input = QLineEdit(str(self.base_config.seed or 0))
            self.seed_input.setPlaceholderText(f"0 到 {MAX_SEED_EXCLUSIVE - 1}")
            self.seed_input.setMinimumWidth(185)
            self.worker_count = QComboBox()
            self.populate_worker_options()
            self.worker_count.setToolTip("多輪模擬使用的 CPU worker 數量")
            self.sort_mode = QComboBox()
            self.sort_mode.addItems(["綜合分數", "勝率", "平均名次"])
            self.run_batch_button = QPushButton("執行多輪模擬")
            self.stop_batch_button = QPushButton("停止模擬")
            controls.addWidget(QLabel("場數"))
            controls.addWidget(self.run_count)
            controls.addWidget(QLabel("Seed"))
            controls.addWidget(self.seed_mode)
            controls.addWidget(self.seed_input)
            controls.addWidget(QLabel("CPU worker"))
            controls.addWidget(self.worker_count)
            controls.addWidget(QLabel("排序"))
            controls.addWidget(self.sort_mode)
            controls.addWidget(self.run_batch_button)
            controls.addWidget(self.stop_batch_button)
            controls.addStretch()
            layout.addLayout(controls)

            progress = QHBoxLayout()
            self.batch_progress = QProgressBar()
            self.batch_progress.setRange(0, 1)
            self.batch_progress.setValue(0)
            self.batch_progress.setFormat("%v / %m")
            self.batch_eta = QLabel("ETA：-")
            progress.addWidget(self.batch_progress, 1)
            progress.addWidget(self.batch_eta)
            layout.addLayout(progress)

            self.results = QTableWidget(0, 6)
            self.results.setHorizontalHeaderLabels(["排名", "團子", "勝場", "勝率", "平均名次", "綜合分數"])
            layout.addWidget(self.results)
            self.run_batch_button.clicked.connect(self.run_batch)
            self.stop_batch_button.clicked.connect(self.stop_batch)
            return box

        def _sync_cards_from_widgets(self) -> None:
            self.cards = [widget.state for widget in self.card_widgets]
            self.refresh_selected_summary()
            self.persist_user_settings()

        def selected_config(self) -> RaceConfig:
            return build_race_config_from_cards(self.base_config, self.cards)

        def refresh_selected_summary(self) -> None:
            selected = [card.name for card in self.cards if card.selected and not card.is_boss]
            self.selected_summary.setText(f"已選 {len(selected)} 顆：{'、'.join(selected) or '尚未選擇'}")

        def start_race(self) -> None:
            try:
                self.configure_race_from_controls()
            except ValueError as exc:
                QMessageBox.warning(self, "設定錯誤", str(exc))
                return
            self.single_race_active = True
            self.stop_auto_timer()
            self.render_state(self.controller.view_state())
            self.apply_control_state()
            self.start_auto_if_checked()

        def reset_race(self) -> None:
            try:
                self.configure_race_from_controls()
            except ValueError as exc:
                QMessageBox.warning(self, "設定錯誤", str(exc))
                return
            self.single_race_active = False
            self.stop_auto_timer()
            self.render_state(self.controller.view_state())
            self.reset_batch_progress()
            self.apply_control_state()

        def configure_race_from_controls(self) -> None:
            self.active_config = self.selected_config()
            mode = self.selected_seed_mode()
            requested_seed = self.fixed_seed_value() if mode is SeedMode.FIXED else None
            resolved_seed = resolve_seed(
                mode=mode,
                requested_seed=requested_seed,
                config_seed=self.active_config.seed,
            )
            self.current_seed = resolved_seed.seed
            self.seed_input.setText(str(self.current_seed))
            self.active_config = replace(self.active_config, seed=self.current_seed)
            self.controller = GuiRaceController(self.active_config)

        def step_race(self) -> None:
            if self.controller is None or not self.single_race_active:
                return
            state = self.controller.step()
            self.render_state(state)
            if state.finished:
                self.stop_auto_timer()

        def start_auto_if_checked(self) -> None:
            if self.auto_play.isChecked():
                self.start_auto()

        def start_auto(self) -> None:
            if not self.single_race_active:
                return
            self.auto_timer.start(self.speed.value())

        def pause_auto(self) -> None:
            self.auto_play.setChecked(False)
            self.stop_auto_timer()

        def stop_auto_timer(self) -> None:
            self.auto_timer.stop()

        def handle_auto_play_changed(self, *_args) -> None:
            if self.auto_play.isChecked():
                self.start_auto()
            else:
                self.stop_auto_timer()
            self.persist_user_settings()

        def render_state(self, state: RaceViewState) -> None:
            self.track_scene.render_state(self.active_config, state)
            actor_name = state.dango_names.get(state.current_actor, state.current_actor or "-")
            round_text = f"第 {state.round_number} 輪" if state.round_number else "尚未開始"
            self.dice_label.setText(
                f"{round_text}｜行動：{actor_name}　骰子："
                f"{state.last_roll if state.last_roll is not None else '-'}"
            )
            self.seed_label.setText(f"目前 seed：{self.current_seed}（{self.selected_seed_mode().value}）")
            self.ranking.clear()
            status = "完賽" if state.finished else "賽中"
            for index, row in enumerate(state.ranking_rows, start=1):
                item = QListWidgetItem(
                    self.piece_icon(row.dango_id, state),
                    f"#{index} {row.name}｜{row.position} 格｜{status}",
                )
                self.ranking.addItem(item)
            self.events.clear()
            for message in state.event_log[-80:]:
                self.events.addItem(format_event_log_message(message))

        def piece_icon(self, dango_id: str, state: RaceViewState) -> QIcon:
            pixmap = QPixmap(26, 26)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(piece_color(dango_id, state)))
            painter.setPen(QPen(QColor("#2f3a44"), 1))
            painter.drawEllipse(2, 2, 22, 22)
            font = QFont()
            font.setBold(True)
            font.setPointSize(9)
            painter.setFont(font)
            painter.setPen(QColor("#101820"))
            painter.drawText(
                pixmap.rect(),
                Qt.AlignmentFlag.AlignCenter,
                state.avatar_labels.get(dango_id, "?"),
            )
            painter.end()
            return QIcon(pixmap)

        def run_batch(self) -> None:
            if self.single_race_active:
                QMessageBox.warning(self, "模擬中", "請先重置單場模擬，再執行多輪模擬。")
                return
            try:
                config = self.selected_config()
                mode = self.selected_seed_mode()
                seed = self.fixed_seed_value() if mode is SeedMode.FIXED else None
                workers = self.selected_workers()
            except ValueError as exc:
                QMessageBox.warning(self, "設定錯誤", str(exc))
                return
            runs = self.run_count.value()
            sample_runs, estimate_seconds, worker_count = self.estimate_batch(config, runs, seed, workers)
            answer = QMessageBox.question(
                self,
                "多輪模擬預估",
                build_batch_estimate_confirmation_message(
                    sample_runs=sample_runs,
                    worker_count=worker_count,
                    total_runs=runs,
                    duration_text=self.format_duration(estimate_seconds),
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.batch_running = True
            self.reset_batch_progress(total=runs)
            self.apply_control_state()
            self.worker = SimulationWorker(config, runs, seed, mode, workers=workers)
            self.worker.finished_with_result.connect(self.render_results)
            self.worker.cancelled_with_result.connect(self.handle_batch_cancelled)
            self.worker.progress_changed.connect(self.update_batch_progress)
            self.worker.failed.connect(self.show_worker_error)
            self.worker.start()

        def render_results(self, result: BatchSimulationResult) -> None:
            self.batch_running = False
            rows = result.rows
            self.current_seed = result.seed
            self.seed_input.setText(str(result.seed))
            self.seed_label.setText(f"目前 seed：{self.current_seed}（{result.seed_mode.value}）")
            self.update_batch_progress(result.completed_runs, result.total_runs, 0.0)
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
            self.apply_control_state()

        def show_worker_error(self, message: str) -> None:
            self.batch_running = False
            self.apply_control_state()
            QMessageBox.warning(self, "模擬失敗", message)

        def stop_batch(self) -> None:
            if self.worker is None or not self.batch_running:
                return
            self.stop_batch_button.setEnabled(False)
            self.batch_eta.setText("ETA：正在停止...")
            self.worker.cancel()

        def handle_batch_cancelled(self, result: BatchSimulationResult) -> None:
            self.batch_running = False
            self.update_batch_progress(result.completed_runs, result.total_runs, 0.0)
            self.batch_eta.setText(f"已停止：{result.completed_runs} / {result.total_runs}")
            self.apply_control_state()

        def update_batch_progress(self, completed: int, total: int, eta_seconds: float) -> None:
            self.batch_progress.setRange(0, max(1, total))
            self.batch_progress.setValue(completed)
            self.batch_progress.setFormat(f"{completed} / {total}")
            self.batch_eta.setText(f"ETA：{self.format_duration(eta_seconds)}")

        def reset_batch_progress(self, total: int | None = None) -> None:
            maximum = total or 1
            self.batch_progress.setRange(0, maximum)
            self.batch_progress.setValue(0)
            self.batch_progress.setFormat(f"0 / {maximum if total else 0}")
            self.batch_eta.setText("ETA：-")

        def estimate_batch(
            self,
            config: RaceConfig,
            runs: int,
            seed: int | None,
            workers: int | str | None,
        ) -> tuple[int, float, int]:
            sample_runs = estimate_sample_runs(runs)
            sample_seed = seed if seed is not None else config.seed or 0
            started_at = time.perf_counter()
            run_batch_simulation(config, runs=sample_runs, seed=sample_seed, seed_mode=SeedMode.FIXED, workers=1)
            elapsed = time.perf_counter() - started_at
            worker_count = resolve_worker_count(workers, runs=runs)
            sequential_estimate = estimate_seconds_from_sample(
                elapsed_seconds=elapsed,
                sample_runs=sample_runs,
                total_runs=runs,
            )
            parallel_estimate = sequential_estimate / worker_count
            return sample_runs, parallel_estimate, worker_count

        def apply_control_state(self) -> None:
            simulation_active = self.single_race_active or self.batch_running
            self.set_participant_controls_enabled(not simulation_active)

            self.start_button.setEnabled(not simulation_active)
            self.step_button.setEnabled(self.single_race_active)
            self.auto_play.setEnabled(
                is_auto_play_control_enabled(
                    single_race_active=self.single_race_active,
                    batch_running=self.batch_running,
                )
            )
            self.pause_button.setEnabled(self.single_race_active)
            self.reset_button.setEnabled(self.single_race_active)
            self.speed.setEnabled(True)

            batch_controls_enabled = not self.batch_running and not self.single_race_active
            self.run_count.setEnabled(batch_controls_enabled)
            self.seed_mode.setEnabled(batch_controls_enabled)
            self.seed_input.setEnabled(
                is_seed_input_enabled(
                    seed_mode=str(self.seed_mode.currentData()),
                    batch_controls_enabled=batch_controls_enabled,
                )
            )
            self.worker_count.setEnabled(batch_controls_enabled)
            self.run_batch_button.setEnabled(batch_controls_enabled)
            self.stop_batch_button.setEnabled(self.batch_running)
            self.sort_mode.setEnabled(True)

        def set_participant_controls_enabled(self, enabled: bool) -> None:
            for widget in self.card_widgets:
                widget.set_editing_enabled(enabled)

        def format_duration(self, seconds: float) -> str:
            seconds = max(0, int(round(seconds)))
            minutes, remaining_seconds = divmod(seconds, 60)
            hours, remaining_minutes = divmod(minutes, 60)
            if hours:
                return f"{hours} 小時 {remaining_minutes} 分 {remaining_seconds} 秒"
            if remaining_minutes:
                return f"{remaining_minutes} 分 {remaining_seconds} 秒"
            return f"{remaining_seconds} 秒"

        def selected_seed_mode(self) -> SeedMode:
            return SeedMode(self.seed_mode.currentData())

        def selected_workers(self) -> str:
            return str(self.worker_count.currentData())

        def populate_worker_options(self) -> None:
            self.worker_count.addItem("自動", "auto")
            self.worker_count.addItem("全力", "full")
            max_workers = max(1, os.cpu_count() or 1)
            for count in range(1, max_workers + 1):
                self.worker_count.addItem(str(count), str(count))

        def fixed_seed_value(self) -> int:
            raw_seed = self.seed_input.text().strip()
            if not raw_seed:
                raise ValueError("固定 seed 必須是非負整數。")
            try:
                seed = int(raw_seed)
            except ValueError as exc:
                raise ValueError("固定 seed 必須是非負整數。") from exc
            if seed < 0 or seed >= MAX_SEED_EXCLUSIVE:
                raise ValueError(f"固定 seed 必須介於 0 到 {MAX_SEED_EXCLUSIVE - 1}。")
            return seed

        def apply_loaded_settings_to_controls(self) -> None:
            self.speed.setValue(self.user_settings.single_race.speed_ms)
            self.auto_play.setChecked(self.user_settings.single_race.auto_play)
            self.run_count.setValue(self.user_settings.batch_simulation.runs)
            self.set_combo_current_data(self.seed_mode, self.user_settings.batch_simulation.seed_mode)
            self.seed_input.setText(self.user_settings.batch_simulation.seed)
            self.set_combo_current_data(self.worker_count, self.user_settings.batch_simulation.workers)
            self.set_combo_current_text(self.sort_mode, self.user_settings.batch_simulation.sort_mode)

        def connect_settings_persistence(self) -> None:
            self.speed.valueChanged.connect(self.persist_user_settings)
            self.run_count.valueChanged.connect(self.persist_user_settings)
            self.seed_mode.currentIndexChanged.connect(self.handle_seed_mode_changed)
            self.seed_input.textChanged.connect(self.persist_user_settings)
            self.worker_count.currentIndexChanged.connect(self.persist_user_settings)
            self.sort_mode.currentIndexChanged.connect(self.persist_user_settings)

        def handle_seed_mode_changed(self, *_args) -> None:
            self.apply_control_state()
            self.persist_user_settings()

        def current_user_settings(self) -> UserSettings:
            selected_ids = tuple(card.dango_id for card in self.cards if card.selected and not card.is_boss)
            boss_card = next((card for card in self.cards if card.is_boss), None)
            boss_mode = (boss_card.boss_mode if boss_card is not None else BossMode.DISRUPTOR).value
            return UserSettings(
                participants=ParticipantSettings(
                    selected_dango_ids=selected_ids,
                    boss_mode=boss_mode,
                ),
                single_race=SingleRaceSettings(speed_ms=self.speed.value(), auto_play=self.auto_play.isChecked()),
                batch_simulation=BatchSimulationSettings(
                    runs=self.run_count.value(),
                    seed_mode=str(self.seed_mode.currentData()),
                    seed=self.seed_input.text().strip(),
                    sort_mode=self.sort_mode.currentText(),
                    workers=str(self.worker_count.currentData()),
                ),
            )

        def persist_user_settings(self, *_args) -> None:
            if self.loading_settings:
                return
            self.user_settings = self.current_user_settings()
            try:
                self.settings_store.save(self.user_settings)
            except OSError as exc:
                self.statusBar().showMessage(f"設定儲存失敗：{exc}", 5000)

        def set_combo_current_data(self, combo: QComboBox, value: str) -> None:
            index = combo.findData(value)
            if index >= 0:
                combo.setCurrentIndex(index)

        def set_combo_current_text(self, combo: QComboBox, value: str) -> None:
            index = combo.findText(value)
            if index >= 0:
                combo.setCurrentIndex(index)

        def closeEvent(self, event) -> None:
            self.persist_user_settings()
            super().closeEvent(event)

    app = QApplication([])
    window = MainWindow()
    window.resize(1280, 820)
    window.show()
    if os.environ.get("DANGOSIM_GUI_SMOKE") == "1":
        QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(run())
