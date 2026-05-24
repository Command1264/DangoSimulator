from __future__ import annotations

import json
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
from dangosim.gui.number_formatting import (
    apply_group_separator_delete,
    format_grouped_int,
    normalize_grouped_int_text,
    parse_grouped_int,
)
from dangosim.gui.services import BatchSimulationResult, GuiRaceController, run_batch_simulation
from dangosim.gui.settings import (
    BatchSimulationSettings,
    MAX_BATCH_RUNS,
    ParticipantOverrideSettings,
    ParticipantSettings,
    SingleRaceSettings,
    UserSettings,
    UserSettingsStore,
    apply_settings_to_cards,
)
from dangosim.gui.tooltips import TooltipRect, TooltipSize, choose_tooltip_position
from dangosim.gui.view_models import (
    BossMode,
    ParticipantCardState,
    RaceViewState,
    SimulationResultRow,
    avatar_label_for_name,
    build_participant_cards,
    build_race_config_from_cards,
    dango_display_name,
    format_event_log_message,
    is_auto_play_control_enabled,
    is_seed_input_enabled,
    participant_card_layout_spec,
    participant_selection_summary,
    track_cell_tooltip,
)
from dangosim.randomness import MAX_SEED_EXCLUSIVE, SeedMode, resolve_seed
from dangosim.resources import resource_path

APP_TITLE = "DangoSimulator 小團快跑模擬器"


def run() -> int:
    multiprocessing.freeze_support()
    try:
        from PySide6.QtCore import QPoint, QThread, QTimer, Qt, Signal
        from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap, QValidator
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QFrame,
            QGraphicsEllipseItem,
            QGraphicsScene,
            QGraphicsTextItem,
            QGraphicsView,
            QGridLayout,
            QGroupBox,
            QHeaderView,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QMainWindow,
            QMessageBox,
            QProgressBar,
            QPushButton,
            QScrollArea,
            QSizePolicy,
            QSpinBox,
            QSplitter,
            QStackedWidget,
            QTabBar,
            QTableWidget,
            QTableWidgetItem,
            QToolTip,
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
    RESULT_TABLE_MIN_VISIBLE_ROWS = 7
    RESULT_TABLE_ROW_HEIGHT = 28
    RESULT_TABLE_HEADERS = ["排名", "團子", "勝場", "勝率", "平均名次", "綜合分數"]
    RESULT_SORT_COLUMNS = {
        1: ("name", "團子"),
        2: ("wins", "勝場"),
        3: ("win_rate", "勝率"),
        4: ("average_rank", "平均名次"),
        5: ("weighted_score", "綜合分數"),
    }
    RESULT_SORT_INDEX_BY_COLUMN = {
        column: index
        for index, (column, _label) in RESULT_SORT_COLUMNS.items()
    }
    RESULT_SORT_LABEL_BY_COLUMN = {
        column: label
        for _index, (column, label) in RESULT_SORT_COLUMNS.items()
    }
    DEFAULT_RESULT_SORT_COLUMN = "weighted_score"
    DEFAULT_RESULT_SORT_DIRECTION = "desc"
    # 左右資訊欄固定等寬，避免 table/list minimum width 在視窗縮放時把賽道中心拉偏。
    SINGLE_INFO_PANEL_WIDTH = 340

    class GroupedIntegerSpinBox(QSpinBox):
        def __init__(self) -> None:
            super().__init__()
            self._updating_grouped_text = False
            self.setKeyboardTracking(True)
            self.lineEdit().textEdited.connect(self._format_edited_text)

        def textFromValue(self, value: int) -> str:
            return format_grouped_int(value)

        def valueFromText(self, text: str) -> int:
            return parse_grouped_int(text, default=self.minimum())

        def validate(self, text: str, position: int) -> tuple[QValidator.State, str, int]:
            digits = "".join(character for character in text if character.isdigit())
            if not digits:
                return (QValidator.State.Intermediate, text, position)
            if any(character not in "0123456789," for character in text):
                return (QValidator.State.Invalid, text, position)
            value = int(digits)
            if self.minimum() <= value <= self.maximum():
                return (QValidator.State.Acceptable, text, position)
            return (QValidator.State.Intermediate, text, position)

        def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
            line_edit = self.lineEdit()
            if not line_edit.hasSelectedText() and event.key() in {
                Qt.Key.Key_Backspace,
                Qt.Key.Key_Delete,
            }:
                key = "backspace" if event.key() == Qt.Key.Key_Backspace else "delete"
                edit = apply_group_separator_delete(
                    line_edit.text(),
                    cursor_position=line_edit.cursorPosition(),
                    key=key,
                )
                if edit is not None:
                    self._apply_normalized_text(
                        normalize_grouped_int_text(
                            edit.text,
                            cursor_position=0,
                            minimum=self.minimum(),
                            maximum=self.maximum(),
                            digit_cursor=edit.digit_cursor,
                            cursor_from_right=edit.cursor_from_right,
                        )
                    )
                    event.accept()
                    return
            super().keyPressEvent(event)

        def _format_edited_text(self, text: str) -> None:
            if self._updating_grouped_text:
                return
            self._apply_normalized_text(
                normalize_grouped_int_text(
                    text,
                    cursor_position=self.lineEdit().cursorPosition(),
                    minimum=self.minimum(),
                    maximum=self.maximum(),
                )
            )

        def _apply_normalized_text(self, normalized) -> None:  # type: ignore[no-untyped-def]
            self._updating_grouped_text = True
            try:
                if normalized.value != self.value():
                    self.setValue(normalized.value)
                self.lineEdit().setText(normalized.text)
                self.lineEdit().setCursorPosition(normalized.cursor_position)
            finally:
                self._updating_grouped_text = False

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

        def helpEvent(self, event) -> None:  # noqa: N802 - Qt override name
            item = next((candidate for candidate in self.items(event.scenePos()) if candidate.toolTip()), None)
            if item is None:
                QToolTip.hideText()
                event.ignore()
                return
            view = self._view_for_tooltip(event.widget())
            if view is None:
                QToolTip.showText(event.screenPos(), item.toolTip())
                event.accept()
                return
            QToolTip.showText(self._tooltip_global_position(view, item, item.toolTip()), item.toolTip(), view.viewport())
            event.accept()

        def _view_for_tooltip(self, widget):
            views = self.views()
            if not views:
                return None
            if widget is not None:
                for view in views:
                    if view.viewport() is widget:
                        return view
            return views[0]

        def _tooltip_global_position(self, view, item, text: str) -> QPoint:
            scene_rect = item.sceneBoundingRect()
            top_left = view.mapFromScene(scene_rect.topLeft())
            bottom_right = view.mapFromScene(scene_rect.bottomRight())
            left = min(top_left.x(), bottom_right.x())
            top = min(top_left.y(), bottom_right.y())
            right = max(top_left.x(), bottom_right.x())
            bottom = max(top_left.y(), bottom_right.y())
            target_top_left = view.viewport().mapToGlobal(QPoint(left, top))
            viewport_top_left = view.viewport().mapToGlobal(QPoint(0, 0))
            metrics = QFontMetrics(QToolTip.font())
            text_rect = metrics.boundingRect(text)
            x, y = choose_tooltip_position(
                target=TooltipRect(
                    x=target_top_left.x(),
                    y=target_top_left.y(),
                    width=max(1, right - left),
                    height=max(1, bottom - top),
                ),
                tooltip=TooltipSize(width=text_rect.width() + 18, height=text_rect.height() + 12),
                viewport=TooltipRect(
                    x=viewport_top_left.x(),
                    y=viewport_top_left.y(),
                    width=view.viewport().width(),
                    height=view.viewport().height(),
                ),
            )
            return QPoint(x, y)

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
                is_midpoint = math.isclose(float(config.track.midpoint), float(index))
                color = {
                    "advance": "#65c56f",
                    "block": "#e37272",
                    "time_rift": "#9270d8",
                }.get(device, "#f0c64a" if is_midpoint else "#d8e1ea")
                pen_color = "#d2a72c" if is_midpoint else "#6a7783"
                item = self.addEllipse(x - 9, y - 9, 18, 18, QPen(QColor(pen_color), 2 if is_midpoint else 1), QColor(color))
                item.setZValue(10)
                item.setToolTip(track_cell_tooltip(index=index, device=device, is_midpoint=is_midpoint))
                if index == config.track.finish:
                    finish_label = self.addText("終")
                    finish_label.setZValue(20)
                    finish_label.setPos(x - 11, y - 34)
                if is_midpoint:
                    midpoint_label = self.addText("中")
                    midpoint_label.setDefaultTextColor(QColor("#8a6a00"))
                    midpoint_label.setZValue(20)
                    midpoint_label.setPos(x - 11, y + 11)

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
                piece.setToolTip(dango_display_name(dango_id, state.dango_names))
                self.addItem(piece)
                if dango_id == state.current_actor:
                    highlight = QGraphicsEllipseItem(x - 19, y - 32 + offset_y, 38, 38)
                    highlight.setBrush(QColor(0, 0, 0, 0))
                    highlight.setPen(QPen(QColor("#f0c64a"), 3))
                    highlight.setZValue(layer.highlight_z)
                    self.addItem(highlight)
                label = QGraphicsTextItem(
                    state.avatar_labels.get(
                        dango_id,
                        avatar_label_for_name(dango_display_name(dango_id, state.dango_names)),
                    )
                )
                label.setDefaultTextColor(QColor("#101820"))
                label.setZValue(layer.label_z)
                label.setPos(x - 12, y - 26 + offset_y)
                self.addItem(label)

    class WheelTransparentSpinBox(QSpinBox):
        def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override name
            event.ignore()

    class WheelTransparentComboBox(QComboBox):
        def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override name
            event.ignore()

    class ParticipantCard(QFrame):
        def __init__(
            self,
            state: ParticipantCardState,
            on_change: Callable[[], None],
            *,
            track_length: int,
            order_limit: int,
        ) -> None:
            super().__init__()
            self.state = state
            self.on_change = on_change
            self.track_length = track_length
            self.order_limit = max(1, order_limit)
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setMinimumWidth(190)
            layout = QVBoxLayout(self)
            layout.setSpacing(8)
            badge_row = QHBoxLayout()
            if state.group:
                group = QLabel(state.group)
                group.setAlignment(Qt.AlignmentFlag.AlignCenter)
                group.setMinimumWidth(24)
                group.setFixedHeight(24)
                group.setStyleSheet(
                    "border-radius: 12px;"
                    "padding: 2px 7px;"
                    "background: #d9effa;"
                    "color: #3d6980;"
                    "font-weight: 700;"
                )
                badge_row.addWidget(group, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            badge_row.addStretch(1)
            layout.addLayout(badge_row)

            identity = QVBoxLayout()
            identity.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar = QLabel(avatar_label_for_name(state.name))
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar.setFixedSize(52, 52)
            avatar.setStyleSheet("border-radius: 26px; background: #d9effa; font-size: 20px; font-weight: 700;")
            identity.addWidget(avatar, 0, Qt.AlignmentFlag.AlignCenter)
            name = QLabel(state.name)
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name.setWordWrap(True)
            name.setStyleSheet("font-weight: 700;")
            identity.addWidget(name, 0, Qt.AlignmentFlag.AlignCenter)
            layout.addLayout(identity)
            note = QLabel(state.skill_note)
            note.setObjectName("skill_note")
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            note.setWordWrap(True)
            note.setStyleSheet(
                "QLabel {"
                "border: 1px solid #c9dce8;"
                "border-radius: 6px;"
                "padding: 6px;"
                "background: rgba(255, 255, 255, 0.55);"
                "}"
            )
            self.skill_note_label = note
            layout.addWidget(note)
            self.position = WheelTransparentSpinBox()
            self.position.setRange(1, self.track_length)
            self.position.setValue(min(max(1, state.start_position), self.track_length))
            self.stack_order = self._order_combo(state.initial_stack_order)
            self.first_round_order = self._order_combo(state.first_round_order)
            layout.addWidget(QLabel("初始位置"))
            layout.addWidget(self.position)
            order_row = QHBoxLayout()
            stack_column = QVBoxLayout()
            stack_column.addWidget(QLabel("初始堆疊"))
            stack_column.addWidget(self.stack_order)
            first_round_column = QVBoxLayout()
            first_round_column.addWidget(QLabel("首回合順序"))
            first_round_column.addWidget(self.first_round_order)
            order_row.addLayout(stack_column, 1)
            order_row.addLayout(first_round_column, 1)
            layout.addLayout(order_row)
            self.mode = WheelTransparentComboBox()
            self.mode.addItem("干擾者", BossMode.DISRUPTOR.value)
            self.mode.addItem("參賽者", BossMode.RANKED.value)
            self.mode.setVisible(state.is_boss)
            self.mode.setCurrentIndex(1 if state.boss_mode is BossMode.RANKED else 0)
            layout.addWidget(self.mode)
            self.position.valueChanged.connect(self._changed)
            self.stack_order.currentIndexChanged.connect(self._changed)
            self.first_round_order.currentIndexChanged.connect(self._changed)
            self.mode.currentIndexChanged.connect(self._changed)
            self._refresh_card_state()

        def _order_combo(self, value: int | None) -> QComboBox:
            combo = WheelTransparentComboBox()
            combo.addItem("隨機", None)
            for order in range(1, self.order_limit + 1):
                combo.addItem(str(order), order)
            if value is not None:
                index = combo.findData(value)
                if index >= 0:
                    combo.setCurrentIndex(index)
            return combo

        def mousePressEvent(self, event) -> None:
            child = self.childAt(event.position().toPoint())
            clicked_edit_control = any(
                self._is_child_widget(child, widget)
                for widget in [self.position, self.stack_order, self.first_round_order, self.mode]
            )
            if clicked_edit_control and self.state.selected:
                super().mousePressEvent(event)
                return
            if self.state.is_boss:
                event.accept()
                return
            self.state = self.state.with_updates(selected=not self.state.selected)
            self._refresh_card_state()
            self.on_change()
            event.accept()

        def _is_child_widget(self, child, widget) -> bool:
            while child is not None:
                if child is widget:
                    return True
                child = child.parentWidget()
            return False

        def _changed(self) -> None:
            mode = BossMode(self.mode.currentData()) if self.state.is_boss else BossMode.NONE
            self.state = self.state.with_updates(
                selected=self.state.selected,
                boss_mode=mode,
                start_position=self.position.value(),
            ).with_order_updates(
                initial_stack_order=self.stack_order.currentData(),
                first_round_order=self.first_round_order.currentData(),
            )
            self._refresh_card_state()
            self.on_change()

        def set_editing_enabled(self, enabled: bool) -> None:
            self.setEnabled(enabled)

        def _refresh_card_state(self) -> None:
            controls_enabled = self.state.selected
            for widget in [self.position, self.stack_order, self.first_round_order, self.mode]:
                widget.setEnabled(controls_enabled)
            border = "#5db7e8" if self.state.selected else "#c9dce8"
            background = "#eefaff" if self.state.selected else "#f5fafc"
            self.setStyleSheet(
                "QFrame {"
                f"border: 2px solid {border};"
                "border-radius: 8px;"
                "padding: 6px;"
                f"background: {background};"
                "}"
            )

    class ParticipantSetupDialog(QDialog):
        def __init__(self, cards: list[ParticipantCardState], *, track_length: int, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            layout_spec = participant_card_layout_spec()
            self.setWindowTitle("自訂參賽團子")
            self.resize(940, 720)
            self.card_widgets: list[ParticipantCard] = []
            layout = QVBoxLayout(self)
            header = QHBoxLayout()
            title = QVBoxLayout()
            title_label = QLabel("自訂參賽團子")
            title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
            self.count_label = QLabel()
            self.count_label.setWordWrap(True)
            self.count_label.setMinimumWidth(0)
            # Long participant names should wrap inside the current dialog width
            # instead of increasing the dialog's horizontal size hint.
            self.count_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            title.addWidget(title_label)
            title.addWidget(self.count_label)
            header.addLayout(title, 1)
            header.addWidget(QLabel("地圖"))
            self.map_selector = WheelTransparentComboBox()
            self.map_selector.addItem("預設賽道")
            self.map_selector.setEnabled(False)
            header.addWidget(self.map_selector)
            layout.addLayout(header)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            if not layout_spec.allow_horizontal_scroll:
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            body = QWidget()
            grid = QGridLayout(body)
            for index, card in enumerate(cards):
                widget = ParticipantCard(
                    card,
                    self._card_changed,
                    track_length=track_length,
                    order_limit=len(cards),
                )
                self.card_widgets.append(widget)
                grid.addWidget(widget, index // layout_spec.columns, index % layout_spec.columns)
            scroll.setWidget(body)
            layout.addWidget(scroll, 1)

            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText("確認")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
            buttons.accepted.connect(self._accept_if_valid)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)
            self._refresh_count()
            self._equalize_skill_note_heights(layout_spec.columns)

        def cards(self) -> list[ParticipantCardState]:
            return [widget.state for widget in self.card_widgets]

        def _card_changed(self) -> None:
            self._refresh_count()

        def _refresh_count(self) -> None:
            self.count_label.setText(participant_selection_summary(self.cards()))

        def _equalize_skill_note_heights(self, columns: int) -> None:
            for index in range(0, len(self.card_widgets), columns):
                row_cards = self.card_widgets[index : index + columns]
                for card in row_cards:
                    card.skill_note_label.setMinimumHeight(0)
                    card.skill_note_label.setMaximumHeight(16777215)
                    card.skill_note_label.updateGeometry()
                row_height = max(card.skill_note_label.sizeHint().height() for card in row_cards)
                for card in row_cards:
                    card.skill_note_label.setFixedHeight(row_height)

        def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override name
            super().resizeEvent(event)
            self._equalize_skill_note_heights(participant_card_layout_spec().columns)

        def _accept_if_valid(self) -> None:
            if not any(card.selected and not card.is_boss for card in self.cards()):
                QMessageBox.warning(self, "設定錯誤", "至少選擇 1 顆一般團子。")
                return
            self.accept()

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
            self.single_current_seed = self.current_seed
            self.single_seed_mode = SeedMode.FIXED
            self.single_race_active = False
            self.batch_running = False
            self.batch_result_rows: list[SimulationResultRow] = []
            self.batch_sort_column = DEFAULT_RESULT_SORT_COLUMN
            self.batch_sort_direction = DEFAULT_RESULT_SORT_DIRECTION

            self.auto_timer = QTimer(self)
            self.auto_timer.timeout.connect(self.step_race)

            self.setCentralWidget(self._build_shell())

            self.apply_loaded_settings_to_controls()
            self.refresh_selected_summary()
            self.reset_race()
            self.loading_settings = False
            self.connect_settings_persistence()
            self.persist_user_settings()

        def _build_shell(self) -> QWidget:
            root = QWidget()
            root.setObjectName("workspace_shell")
            layout = QVBoxLayout(root)
            layout.setContentsMargins(8, 8, 8, 8)

            self.workspace_nav = QTabBar()
            self.workspace_nav.setObjectName("workspace_nav")
            self.workspace_nav.addTab("單輪模擬")
            self.workspace_nav.addTab("多輪模擬")
            self.workspace_nav.addTab("設定")
            self.workspace_nav.setExpanding(False)
            self.workspace_nav.setDocumentMode(True)

            self.workspace_stack = QStackedWidget()
            self.workspace_stack.setObjectName("workspace_stack")
            self.workspace_stack.addWidget(self._build_single_race_workspace())
            self.workspace_stack.addWidget(self._build_results_panel())
            self.workspace_stack.addWidget(self._build_settings_workspace())

            self.workspace_nav.currentChanged.connect(self.workspace_stack.setCurrentIndex)
            self.workspace_nav.setCurrentIndex(0)

            layout.addWidget(self.workspace_nav, 0, Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(self.workspace_stack, 1)
            return root

        def _build_single_race_workspace(self) -> QWidget:
            workspace = QWidget()
            workspace.setObjectName("single_race_workspace")
            layout = QVBoxLayout(workspace)

            main_splitter = QSplitter(Qt.Orientation.Horizontal)
            main_splitter.setObjectName("main_splitter")
            self.main_splitter = main_splitter
            main_splitter.addWidget(self._build_left_panel())
            main_splitter.addWidget(self._build_center_panel())
            main_splitter.addWidget(self._build_right_panel())
            main_splitter.setChildrenCollapsible(False)
            main_splitter.setStretchFactor(0, 0)
            main_splitter.setStretchFactor(1, 1)
            main_splitter.setStretchFactor(2, 0)
            main_splitter.setSizes([SINGLE_INFO_PANEL_WIDTH, 760, SINGLE_INFO_PANEL_WIDTH])
            layout.addWidget(main_splitter, 1)
            return workspace

        def _build_left_panel(self) -> QWidget:
            panel = QWidget()
            panel.setObjectName("left_panel")
            panel.setFixedWidth(SINGLE_INFO_PANEL_WIDTH)
            layout = QVBoxLayout(panel)
            self.events = QListWidget()
            self.events.setObjectName("event_log")
            layout.addWidget(QLabel("事件紀錄"))
            layout.addWidget(self.events, 1)
            return panel

        def _build_center_panel(self) -> QWidget:
            panel = QWidget()
            panel.setObjectName("center_panel")
            layout = QVBoxLayout(panel)
            self.title_label = QLabel(APP_TITLE)
            self.title_label.setObjectName("app_title")
            self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.title_label.setStyleSheet("font-size: 20px; font-weight: 700;")
            layout.addWidget(self.title_label)
            self.track_scene = TrackScene(panel)
            view = QGraphicsView(self.track_scene)
            view.setObjectName("track_view")
            self.track_view = view
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
            panel.setObjectName("right_panel")
            panel.setFixedWidth(SINGLE_INFO_PANEL_WIDTH)
            layout = QVBoxLayout(panel)
            self.ranking = QTableWidget(0, 4)
            self.ranking.setObjectName("ranking_table")
            self.ranking.setHorizontalHeaderLabels(["名次", "團子", "格數", "狀態"])
            self._configure_table(self.ranking)
            self.round_actions = QTableWidget(0, 4)
            self.round_actions.setObjectName("round_action_table")
            self.round_actions.setHorizontalHeaderLabels(["順序", "團子", "骰子", "狀態"])
            self._configure_table(self.round_actions)
            layout.addWidget(QLabel("即時名次"))
            layout.addWidget(self.ranking, 1)
            layout.addWidget(QLabel("本輪行動"))
            layout.addWidget(self.round_actions, 1)
            return panel

        def _configure_table(self, table: QTableWidget) -> None:
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setAlternatingRowColors(True)
            table.setShowGrid(False)

        def _build_results_panel(self) -> QWidget:
            box = QGroupBox("多輪模擬")
            box.setObjectName("batch_simulation_workspace")
            layout = QVBoxLayout(box)
            controls = QHBoxLayout()
            self.run_count = GroupedIntegerSpinBox()
            self.run_count.setRange(1, MAX_BATCH_RUNS)
            self.run_count.setValue(1000)
            self.run_count.setMinimumWidth(145)
            self.worker_count = QComboBox()
            self.populate_worker_options()
            self.worker_count.setToolTip("多輪模擬使用的 CPU worker 數量")
            self.run_batch_button = QPushButton("執行多輪模擬")
            self.stop_batch_button = QPushButton("停止模擬")
            controls.addWidget(QLabel("場數"))
            controls.addWidget(self.run_count)
            controls.addWidget(QLabel("CPU worker"))
            controls.addWidget(self.worker_count)
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
            self.update_result_headers()
            self.results.horizontalHeader().setSectionsClickable(True)
            self.results.verticalHeader().setDefaultSectionSize(RESULT_TABLE_ROW_HEIGHT)
            result_header_height = self.results.horizontalHeader().sizeHint().height()
            self.results.setMinimumHeight(
                result_header_height
                + (RESULT_TABLE_ROW_HEIGHT * RESULT_TABLE_MIN_VISIBLE_ROWS)
                + (self.results.frameWidth() * 2)
                + 12
            )
            layout.addWidget(self.results)
            self.run_batch_button.clicked.connect(self.run_batch)
            self.stop_batch_button.clicked.connect(self.stop_batch)
            self.results.horizontalHeader().sectionClicked.connect(self.handle_result_header_clicked)
            return box

        def _build_settings_workspace(self) -> QWidget:
            workspace = QWidget()
            workspace.setObjectName("settings_workspace")
            layout = QVBoxLayout(workspace)

            title = QLabel("設定")
            title.setStyleSheet("font-size: 18px; font-weight: 700;")
            layout.addWidget(title)

            layout.addWidget(QLabel("目前參賽團子"))
            self.settings_selected_summary = QLabel()
            self.settings_selected_summary.setWordWrap(True)
            layout.addWidget(self.settings_selected_summary)

            self.settings_participant_setup_button = QPushButton("自訂參賽團子")
            self.settings_participant_setup_button.clicked.connect(self.open_participant_setup)
            layout.addWidget(self.settings_participant_setup_button)

            separator = QFrame()
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setFrameShadow(QFrame.Shadow.Sunken)
            layout.addWidget(separator)

            layout.addWidget(QLabel("Seed 設定"))
            seed_panel = QWidget()
            seed_panel.setObjectName("seed_settings_panel")
            seed_layout = QHBoxLayout(seed_panel)
            seed_layout.setContentsMargins(0, 0, 0, 0)
            self.seed_mode = QComboBox()
            self.seed_mode.setObjectName("seed_mode")
            self.seed_mode.addItem("固定 seed", SeedMode.FIXED.value)
            self.seed_mode.addItem("系統隨機 seed", SeedMode.SYSTEM.value)
            self.seed_input = QLineEdit(str(self.base_config.seed or 0))
            self.seed_input.setObjectName("seed_input")
            self.seed_input.setPlaceholderText(f"0 到 {MAX_SEED_EXCLUSIVE - 1}")
            self.seed_input.setMinimumWidth(185)
            self.fixed_seed_label = QLabel("固定 Seed：")
            seed_layout.addWidget(QLabel("Seed 模式"))
            seed_layout.addWidget(self.seed_mode)
            seed_layout.addWidget(self.fixed_seed_label)
            seed_layout.addWidget(self.seed_input)
            seed_layout.addStretch()
            layout.addWidget(seed_panel)

            layout.addWidget(QLabel("單輪模擬設定"))
            self.settings_single_summary = QLabel()
            self.settings_single_summary.setWordWrap(True)
            layout.addWidget(self.settings_single_summary)

            layout.addWidget(QLabel("多輪模擬設定"))
            self.settings_batch_summary = QLabel()
            self.settings_batch_summary.setWordWrap(True)
            layout.addWidget(self.settings_batch_summary)
            layout.addStretch()
            return workspace

        def _sync_cards_from_widgets(self) -> None:
            self.cards = [widget.state for widget in self.card_widgets]
            self.refresh_selected_summary()
            self.persist_user_settings()

        def open_participant_setup(self) -> None:
            dialog = ParticipantSetupDialog(
                self.cards,
                track_length=self.base_config.track.length,
                parent=self,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            self.cards = dialog.cards()
            self.refresh_selected_summary()
            self.persist_user_settings()
            if not self.single_race_active and not self.batch_running:
                self.reset_race()

        def selected_config(self) -> RaceConfig:
            return build_race_config_from_cards(self.base_config, self.cards)

        def refresh_selected_summary(self) -> None:
            summary = participant_selection_summary(self.cards)
            if hasattr(self, "settings_selected_summary"):
                self.settings_selected_summary.setText(summary)
            self.refresh_settings_summary()

        def refresh_settings_summary(self) -> None:
            if not hasattr(self, "settings_single_summary"):
                return
            auto_play_text = "開啟" if self.auto_play.isChecked() else "關閉"
            self.settings_single_summary.setText(
                f"速度：{self.speed.value()} ms\n"
                f"自動播放：{auto_play_text}"
            )
            self.settings_batch_summary.setText(
                f"場數：{self.run_count.text()}\n"
                f"Seed 模式：{self.seed_mode.currentText()}\n"
                f"固定 Seed：{self.seed_input.text().strip() or '-'}\n"
                f"CPU worker：{self.worker_count.currentText()}\n"
                f"結果排序：{self.current_result_sort_label()}"
            )

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
            if not self.batch_running:
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
            self.single_current_seed = resolved_seed.seed
            self.single_seed_mode = mode
            if resolved_seed.mode is SeedMode.FIXED:
                self.seed_input.setText(str(self.current_seed))
            self.active_config = replace(self.active_config, seed=self.single_current_seed)
            self.controller = GuiRaceController(self.active_config)

        def step_race(self) -> None:
            if self.controller is None or not self.single_race_active:
                return
            state = self.controller.step()
            self.render_state(state)
            if state.finished:
                self.single_race_active = False
                self.stop_auto_timer()
                self.apply_control_state()

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
            actor_name = dango_display_name(state.current_actor, state.dango_names)
            round_text = f"第 {state.round_number} 輪" if state.round_number else "尚未開始"
            self.dice_label.setText(
                f"{round_text}｜行動：{actor_name}　骰子："
                f"{state.last_roll if state.last_roll is not None else '-'}"
            )
            self.seed_label.setText(f"目前 seed：{self.single_current_seed}（{self.single_seed_mode.value}）")
            self.render_ranking_table(state)
            self.render_round_action_table(state)
            event_scroll_bar = self.events.verticalScrollBar()
            auto_scroll_events = self.should_auto_scroll_events()
            previous_event_scroll_value = event_scroll_bar.value()
            self.events.clear()
            for message in state.event_log[-80:]:
                self.events.addItem(format_event_log_message(message))
            if auto_scroll_events:
                self.events.scrollToBottom()
            else:
                event_scroll_bar.setValue(min(previous_event_scroll_value, event_scroll_bar.maximum()))

        def should_auto_scroll_events(self) -> bool:
            scroll_bar = self.events.verticalScrollBar()
            return scroll_bar.maximum() <= 0 or scroll_bar.value() >= scroll_bar.maximum()

        def render_ranking_table(self, state: RaceViewState) -> None:
            status = "完賽" if state.finished else "賽中"
            self.ranking.setRowCount(len(state.ranking_rows))
            for row_index, row in enumerate(state.ranking_rows):
                self.set_table_item(
                    self.ranking,
                    row_index,
                    0,
                    str(row_index + 1),
                    alignment=Qt.AlignmentFlag.AlignCenter,
                )
                self.set_table_item(
                    self.ranking,
                    row_index,
                    1,
                    row.name,
                    self.piece_icon(row.dango_id, state),
                    alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                )
                self.set_table_item(
                    self.ranking,
                    row_index,
                    2,
                    str(row.position),
                    alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                )
                self.set_table_item(
                    self.ranking,
                    row_index,
                    3,
                    status,
                    alignment=Qt.AlignmentFlag.AlignCenter,
                )

        def render_round_action_table(self, state: RaceViewState) -> None:
            self.round_actions.setRowCount(len(state.action_rows))
            for row_index, row in enumerate(state.action_rows):
                roll_text = "-" if row.roll is None else str(row.roll)
                self.set_table_item(
                    self.round_actions,
                    row_index,
                    0,
                    str(row.order),
                    alignment=Qt.AlignmentFlag.AlignCenter,
                )
                self.set_table_item(
                    self.round_actions,
                    row_index,
                    1,
                    row.name,
                    self.piece_icon(row.dango_id, state),
                    alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                )
                self.set_table_item(
                    self.round_actions,
                    row_index,
                    2,
                    roll_text,
                    alignment=Qt.AlignmentFlag.AlignCenter,
                )
                self.set_table_item(
                    self.round_actions,
                    row_index,
                    3,
                    row.status,
                    alignment=Qt.AlignmentFlag.AlignCenter,
                )

        def set_table_item(
            self,
            table: QTableWidget,
            row: int,
            column: int,
            text: str,
            icon: QIcon | None = None,
            *,
            alignment: Qt.AlignmentFlag | Qt.Alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        ) -> None:
            item = QTableWidgetItem(text)
            if icon is not None:
                item.setIcon(icon)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(alignment)
            table.setItem(row, column, item)

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
            self.batch_result_rows = list(result.rows)
            self.current_seed = result.seed
            if result.seed_mode is SeedMode.FIXED:
                self.seed_input.setText(str(result.seed))
            if not self.single_race_active:
                self.seed_label.setText(f"目前 seed：{self.current_seed}（{result.seed_mode.value}）")
            self.update_batch_progress(result.completed_runs, result.total_runs, 0.0)
            self.render_result_rows()
            self.apply_control_state()

        def render_result_rows(self) -> None:
            rows = self.sorted_result_rows()
            self.results.setRowCount(len(rows))
            alignments = [
                Qt.AlignmentFlag.AlignCenter,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            ]
            for row_index, row in enumerate(rows):
                visual_rank = row_index + 1
                displayed_rank = visual_rank if self.batch_sort_direction == "desc" else len(rows) - row_index
                values = [
                    str(displayed_rank),
                    row.name,
                    str(row.wins),
                    f"{row.win_rate:.2%}",
                    f"{row.average_rank:.2f}",
                    f"{row.weighted_score:.4f}",
                ]
                for column, value in enumerate(values):
                    self.set_table_item(
                        self.results,
                        visual_rank - 1,
                        column,
                        value,
                        alignment=alignments[column],
                    )

        def sorted_result_rows(self) -> list[SimulationResultRow]:
            column = self.batch_sort_column
            reverse = self.batch_sort_direction == "desc"

            def sort_value(row: SimulationResultRow):
                value = getattr(row, column)
                return value.casefold() if isinstance(value, str) else value

            return sorted(self.batch_result_rows, key=sort_value, reverse=reverse)

        def handle_result_header_clicked(self, column_index: int) -> None:
            if column_index not in RESULT_SORT_COLUMNS:
                return
            column, _label = RESULT_SORT_COLUMNS[column_index]
            if self.batch_sort_column != column:
                self.batch_sort_column = column
                self.batch_sort_direction = "desc"
            elif self.batch_sort_direction == "desc":
                self.batch_sort_direction = "asc"
            else:
                self.batch_sort_column = DEFAULT_RESULT_SORT_COLUMN
                self.batch_sort_direction = DEFAULT_RESULT_SORT_DIRECTION
            self.update_result_headers()
            self.render_result_rows()
            self.persist_user_settings()
            self.refresh_settings_summary()

        def update_result_headers(self) -> None:
            labels = list(RESULT_TABLE_HEADERS)
            sorted_index = RESULT_SORT_INDEX_BY_COLUMN.get(self.batch_sort_column)
            if sorted_index is not None:
                direction_mark = "▼" if self.batch_sort_direction == "desc" else "▲"
                labels[sorted_index] = f"{labels[sorted_index]} {direction_mark}"
            self.results.setHorizontalHeaderLabels(labels)

        def current_result_sort_label(self) -> str:
            label = RESULT_SORT_LABEL_BY_COLUMN.get(self.batch_sort_column, "綜合分數")
            direction = "遞減" if self.batch_sort_direction == "desc" else "遞增"
            return f"{label}（{direction}）"

        def current_result_sort_mode(self) -> str:
            return RESULT_SORT_LABEL_BY_COLUMN.get(self.batch_sort_column, "綜合分數")

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
            # 單輪與多輪可並行；只有會改變兩者共用輸入的設定需要在任一流程執行時鎖住。
            settings_locked = self.single_race_active or self.batch_running
            self.set_participant_controls_enabled(not settings_locked)

            self.start_button.setEnabled(not self.single_race_active)
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

            batch_controls_enabled = not self.batch_running
            seed_controls_enabled = not settings_locked
            self.run_count.setEnabled(batch_controls_enabled)
            self.seed_mode.setEnabled(seed_controls_enabled)
            self.seed_input.setEnabled(
                is_seed_input_enabled(
                    seed_mode=str(self.seed_mode.currentData()),
                    batch_controls_enabled=seed_controls_enabled,
                )
            )
            self.worker_count.setEnabled(batch_controls_enabled)
            self.run_batch_button.setEnabled(batch_controls_enabled)
            self.stop_batch_button.setEnabled(self.batch_running)

        def set_participant_controls_enabled(self, enabled: bool) -> None:
            if hasattr(self, "settings_participant_setup_button"):
                self.settings_participant_setup_button.setEnabled(enabled)

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
            self.refresh_settings_summary()

        def connect_settings_persistence(self) -> None:
            self.speed.valueChanged.connect(self.persist_user_settings)
            self.run_count.valueChanged.connect(self.persist_user_settings)
            self.seed_mode.currentIndexChanged.connect(self.handle_seed_mode_changed)
            self.seed_input.textChanged.connect(self.persist_user_settings)
            self.worker_count.currentIndexChanged.connect(self.persist_user_settings)

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
                    participant_overrides=tuple(
                        ParticipantOverrideSettings(
                            dango_id=card.dango_id,
                            selected=card.selected,
                            start_position=card.start_position,
                            initial_stack_order=card.initial_stack_order,
                            first_round_order=card.first_round_order,
                        )
                        for card in self.cards
                    ),
                ),
                single_race=SingleRaceSettings(speed_ms=self.speed.value(), auto_play=self.auto_play.isChecked()),
                batch_simulation=BatchSimulationSettings(
                    runs=self.run_count.value(),
                    seed_mode=str(self.seed_mode.currentData()),
                    seed=self.seed_input.text().strip(),
                    sort_mode=self.current_result_sort_mode(),
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
            self.refresh_settings_summary()

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
    window.showMaximized()
    app.processEvents()
    if os.environ.get("DANGOSIM_PARTICIPANT_DIALOG_LAYOUT_PROBE") == "1":
        probe_cards = [
            card.with_updates(selected=True)
            if not card.is_boss
            else card.with_updates(selected=True, boss_mode=card.boss_mode)
            for card in window.cards
        ]
        dialog = ParticipantSetupDialog(
            probe_cards,
            track_length=window.base_config.track.length,
            parent=window,
        )
        dialog.show()
        app.processEvents()
        layout_spec = participant_card_layout_spec()

        def horizontal_policy_name(widget: QWidget) -> str:
            return widget.sizePolicy().horizontalPolicy().name

        def alignment_name(label: QLabel) -> str:
            alignment = label.alignment()
            if (
                alignment & Qt.AlignmentFlag.AlignHCenter
                and alignment & Qt.AlignmentFlag.AlignVCenter
            ):
                return "center"
            return "other"

        skill_note_heights_by_row = [
            [
                card.skill_note_label.height()
                for card in dialog.card_widgets[index : index + layout_spec.columns]
            ]
            for index in range(0, len(dialog.card_widgets), layout_spec.columns)
        ]
        probe = {
            "dialog_width": dialog.width(),
            "count_label_width": dialog.count_label.width(),
            "count_label_word_wrap": dialog.count_label.wordWrap(),
            "count_label_horizontal_policy": horizontal_policy_name(dialog.count_label),
            "skill_note_heights_by_row": skill_note_heights_by_row,
            "skill_note_alignments": [
                alignment_name(card.skill_note_label)
                for card in dialog.card_widgets
            ],
        }
        print(json.dumps(probe))
        QTimer.singleShot(0, app.quit)
    elif os.environ.get("DANGOSIM_GUI_CONTROL_STATE_PROBE") == "1":
        def control_snapshot() -> dict[str, bool]:
            return {
                "start": window.start_button.isEnabled(),
                "step": window.step_button.isEnabled(),
                "auto_play": window.auto_play.isEnabled(),
                "pause": window.pause_button.isEnabled(),
                "reset": window.reset_button.isEnabled(),
                "run_batch": window.run_batch_button.isEnabled(),
                "run_count": window.run_count.isEnabled(),
                "worker_count": window.worker_count.isEnabled(),
                "stop_batch": window.stop_batch_button.isEnabled(),
                "participant_setup": window.settings_participant_setup_button.isEnabled(),
                "seed_mode": window.seed_mode.isEnabled(),
                "seed_input": window.seed_input.isEnabled(),
            }

        initial = control_snapshot()
        window.start_race()
        app.processEvents()
        during_single = control_snapshot()
        warning_messages: list[str] = []
        question_messages: list[str] = []
        original_warning = QMessageBox.warning
        original_question = QMessageBox.question
        original_estimate_batch = window.estimate_batch
        QMessageBox.warning = lambda _parent, _title, message: warning_messages.append(message) or QMessageBox.StandardButton.Ok
        QMessageBox.question = (
            lambda _parent, _title, message, *_args: question_messages.append(message) or QMessageBox.StandardButton.No
        )
        window.estimate_batch = lambda _config, runs, _seed, workers: (1, 0.0, resolve_worker_count(workers, runs=runs))
        try:
            window.run_batch()
        finally:
            QMessageBox.warning = original_warning
            QMessageBox.question = original_question
            window.estimate_batch = original_estimate_batch
        during_single_run_batch_attempt = {
            "warning_messages": warning_messages,
            "question_shown": bool(question_messages),
            "batch_running": window.batch_running,
        }
        window.single_race_active = False
        window.batch_running = True
        window.apply_control_state()
        during_batch_only = control_snapshot()
        window.start_race()
        app.processEvents()
        both_active = control_snapshot()
        both_active["single_race_active"] = window.single_race_active
        both_active["batch_running"] = window.batch_running
        seed_label_before_batch_result = window.seed_label.text()
        window.render_results(
            BatchSimulationResult(
                rows=[
                    SimulationResultRow(
                        dango_id="probe",
                        name="測試團子",
                        wins=1,
                        win_rate=1.0,
                        average_rank=1.0,
                        weighted_score=1.0,
                    )
                ],
                seed_mode=SeedMode.SYSTEM,
                seed=123456,
                completed_runs=1,
                total_runs=1,
                cancelled=False,
            )
        )
        seed_label_after_batch_result_while_single_active = window.seed_label.text()
        window.batch_running = True
        window.apply_control_state()
        steps = 0
        while window.single_race_active and steps < 10000:
            window.step_race()
            steps += 1
        app.processEvents()
        after_single_finish_with_batch = control_snapshot()
        after_single_finish_with_batch["single_race_active"] = window.single_race_active
        after_single_finish_with_batch["batch_running"] = window.batch_running
        window.batch_running = False
        window.apply_control_state()
        after_finish = control_snapshot()
        after_finish["single_race_active"] = window.single_race_active
        after_finish["batch_running"] = window.batch_running
        probe = {
            "initial": initial,
            "during_single": during_single,
            "during_single_run_batch_attempt": during_single_run_batch_attempt,
            "during_batch_only": during_batch_only,
            "both_active": both_active,
            "seed_label_before_batch_result": seed_label_before_batch_result,
            "seed_label_after_batch_result_while_single_active": seed_label_after_batch_result_while_single_active,
            "after_single_finish_with_batch": after_single_finish_with_batch,
            "after_finish": after_finish,
            "finished_in_steps": steps,
        }
        print(json.dumps(probe))
        QTimer.singleShot(0, app.quit)
    elif os.environ.get("DANGOSIM_GUI_CONCURRENT_RESET_PROBE") == "1":
        window.start_race()
        window.batch_running = True
        window.update_batch_progress(3, 10, 5.0)
        window.apply_control_state()
        window.reset_race()
        app.processEvents()
        probe = {
            "single_race_active": window.single_race_active,
            "batch_running": window.batch_running,
            "progress_value": window.batch_progress.value(),
            "progress_maximum": window.batch_progress.maximum(),
            "progress_format": window.batch_progress.text(),
            "eta": window.batch_eta.text(),
        }
        print(json.dumps(probe, ensure_ascii=False))
        QTimer.singleShot(0, app.quit)
    elif os.environ.get("DANGOSIM_GUI_SYSTEM_SEED_PROBE") == "1":
        window.configure_race_from_controls()
        fixed_seed_after_single_race_config = window.seed_input.text()
        window.render_results(
            BatchSimulationResult(
                rows=[
                    SimulationResultRow(
                        dango_id="probe",
                        name="測試團子",
                        wins=12,
                        win_rate=0.12,
                        average_rank=2.34,
                        weighted_score=0.5678,
                    )
                ],
                seed_mode=SeedMode.SYSTEM,
                seed=987654,
                completed_runs=100,
                total_runs=100,
                cancelled=False,
            )
        )
        probe = {
            "fixed_seed_label": window.fixed_seed_label.text(),
            "fixed_seed_after_single_race_config": fixed_seed_after_single_race_config,
            "fixed_seed_after_system_batch_result": window.seed_input.text(),
            "current_seed_after_system_batch_result": window.current_seed,
            "seed_label_after_system_batch_result": window.seed_label.text(),
        }
        print(json.dumps(probe))
        QTimer.singleShot(0, app.quit)
    elif os.environ.get("DANGOSIM_GUI_RESULT_SORT_PROBE") == "1":
        window.render_results(
            BatchSimulationResult(
                rows=[
                    SimulationResultRow(
                        dango_id="alpha",
                        name="Alpha",
                        wins=10,
                        win_rate=0.10,
                        average_rank=3.0,
                        weighted_score=0.90,
                    ),
                    SimulationResultRow(
                        dango_id="beta",
                        name="Beta",
                        wins=20,
                        win_rate=0.80,
                        average_rank=2.0,
                        weighted_score=0.50,
                    ),
                    SimulationResultRow(
                        dango_id="gamma",
                        name="Gamma",
                        wins=30,
                        win_rate=0.40,
                        average_rank=1.0,
                        weighted_score=0.70,
                    ),
                ],
                seed_mode=SeedMode.FIXED,
                seed=99,
                completed_runs=100,
                total_runs=100,
                cancelled=False,
            )
        )

        def result_headers() -> list[str]:
            return [
                window.results.horizontalHeaderItem(column).text()
                for column in range(window.results.columnCount())
            ]

        def result_snapshot(*, include_headers: bool = False) -> dict[str, object]:
            snapshot: dict[str, object] = {
                "names": [
                    window.results.item(row, 1).text()
                    for row in range(window.results.rowCount())
                ],
                "ranks": [
                    window.results.item(row, 0).text()
                    for row in range(window.results.rowCount())
                ],
                "state": {
                    "column": window.batch_sort_column,
                    "direction": window.batch_sort_direction,
                },
            }
            if include_headers:
                snapshot["headers"] = result_headers()
            return snapshot

        default = result_snapshot(include_headers=True)
        window.handle_result_header_clicked(3)
        win_rate_desc = result_snapshot()
        window.handle_result_header_clicked(3)
        win_rate_asc = result_snapshot()
        window.handle_result_header_clicked(3)
        win_rate_default = result_snapshot()
        window.handle_result_header_clicked(0)
        after_rank_click = result_snapshot()
        probe = {
            "default": default,
            "win_rate_desc": win_rate_desc,
            "win_rate_asc": win_rate_asc,
            "win_rate_default": win_rate_default,
            "after_rank_click": after_rank_click,
        }
        print(json.dumps(probe))
        QTimer.singleShot(0, app.quit)
    elif os.environ.get("DANGOSIM_GUI_EVENT_SCROLL_PROBE") == "1":
        base_state = window.controller.view_state()

        def state_with_events(prefix: str) -> RaceViewState:
            return replace(
                base_state,
                event_log=tuple(f"{prefix} {index}" for index in range(120)),
            )

        def scroll_snapshot() -> tuple[int, int]:
            scroll_bar = window.events.verticalScrollBar()
            return scroll_bar.value(), scroll_bar.maximum()

        app.processEvents()
        window.events.clear()
        app.processEvents()
        window.render_state(state_with_events("first"))
        app.processEvents()
        first_value, first_maximum = scroll_snapshot()

        window.events.scrollToBottom()
        app.processEvents()
        window.render_state(state_with_events("second"))
        app.processEvents()
        second_value, second_maximum = scroll_snapshot()

        review_target = max(1, second_maximum // 2)
        window.events.verticalScrollBar().setValue(review_target)
        app.processEvents()
        window.render_state(state_with_events("third"))
        app.processEvents()
        review_value, review_maximum = scroll_snapshot()

        probe = {
            "no_scroll_auto_bottom": first_maximum > 0 and first_value == first_maximum,
            "bottom_auto_bottom": second_maximum > 0 and second_value == second_maximum,
            "review_position_preserved": review_value == min(review_target, review_maximum),
        }
        print(json.dumps(probe))
        QTimer.singleShot(0, app.quit)
    elif os.environ.get("DANGOSIM_GUI_LAYOUT_PROBE") == "1":
        window.start_race()
        window.step_race()
        window.render_results(
            BatchSimulationResult(
                rows=[
                    SimulationResultRow(
                        dango_id="probe",
                        name="測試團子",
                        wins=12,
                        win_rate=0.12,
                        average_rank=2.34,
                        weighted_score=0.5678,
                    )
                ],
                seed_mode=SeedMode.FIXED,
                seed=99,
                completed_runs=100,
                total_runs=100,
                cancelled=False,
            )
        )

        def alignment_name(table: QTableWidget, column: int) -> str:
            item = table.item(0, column)
            if item is None:
                return "missing"
            alignment = item.textAlignment()
            if alignment & Qt.AlignmentFlag.AlignRight:
                return "right"
            if alignment & Qt.AlignmentFlag.AlignHCenter:
                return "center"
            return "left"

        def visible_rows(table: QTableWidget) -> int:
            row_height = table.verticalHeader().defaultSectionSize()
            return table.viewport().height() // row_height

        def nav_items(nav: QTabBar | QListWidget) -> list[str]:
            if isinstance(nav, QTabBar):
                return [
                    nav.tabText(index)
                    for index in range(nav.count())
                ]
            return [
                nav.item(index).text()
                for index in range(nav.count())
            ]

        def stack_pages(stack: QStackedWidget) -> list[str]:
            return [
                stack.widget(index).objectName()
                for index in range(stack.count())
            ]

        def ancestor_names(widget: QWidget) -> list[str]:
            names: list[str] = []
            parent = widget.parentWidget()
            while parent is not None:
                if parent.objectName():
                    names.append(parent.objectName())
                parent = parent.parentWidget()
            return names

        def label_texts(widget: QWidget) -> list[str]:
            return [
                label.text()
                for label in widget.findChildren(QLabel)
            ]

        def single_layout_metrics(width: int | None) -> dict[str, int]:
            if width is None:
                window.showMaximized()
            else:
                window.showNormal()
                window.resize(width, 760)
            app.processEvents()
            workspace = window.workspace_stack.currentWidget()
            viewport_center = window.track_view.viewport().mapTo(
                workspace,
                window.track_view.viewport().rect().center(),
            )
            return {
                "map_center_offset": viewport_center.x() - workspace.rect().center().x(),
                "left": window.main_splitter.widget(0).width(),
                "right": window.main_splitter.widget(2).width(),
            }

        batch_workspace = window.workspace_stack.widget(1)
        settings_workspace = window.workspace_stack.widget(2)
        window_maximized = window.isMaximized()
        single_metrics = [
            single_layout_metrics(width)
            for width in (None, 960, 1280, 1600)
        ]

        probe = {
            "window_maximized": window_maximized,
            "workspace_nav_widget_class": type(window.workspace_nav).__name__,
            "workspace_shell_layout": "vertical"
            if isinstance(window.centralWidget().layout(), QVBoxLayout)
            else "other",
            "workspace_nav_items": nav_items(window.workspace_nav),
            "workspace_stack_pages": stack_pages(window.workspace_stack),
            "active_workspace": window.workspace_stack.currentWidget().objectName(),
            "title_parent": window.title_label.parentWidget().objectName(),
            "event_log_parent": window.events.parentWidget().objectName(),
            "splitter_widgets": [
                window.main_splitter.widget(index).objectName()
                for index in range(window.main_splitter.count())
            ],
            "result_table_parent": window.results.parentWidget().objectName(),
            "seed_mode_ancestors": ancestor_names(window.seed_mode),
            "seed_input_ancestors": ancestor_names(window.seed_input),
            "participant_setup_button_ancestors": ancestor_names(window.settings_participant_setup_button),
            "left_panel_labels": label_texts(window.main_splitter.widget(0)),
            "batch_workspace_labels": label_texts(batch_workspace),
            "settings_workspace_labels": label_texts(settings_workspace),
            "ranking_alignment": [
                alignment_name(window.ranking, column)
                for column in range(window.ranking.columnCount())
            ],
            "round_action_alignment": [
                alignment_name(window.round_actions, column)
                for column in range(window.round_actions.columnCount())
            ],
            "result_alignment": [
                alignment_name(window.results, column)
                for column in range(window.results.columnCount())
            ],
            "result_visible_rows": visible_rows(window.results),
            "single_map_center_offsets": [
                metric["map_center_offset"]
                for metric in single_metrics
            ],
            "single_info_panel_widths": [
                {"left": metric["left"], "right": metric["right"]}
                for metric in single_metrics
            ],
        }
        print(json.dumps(probe))
        QTimer.singleShot(0, app.quit)
    elif os.environ.get("DANGOSIM_GUI_SMOKE") == "1":
        QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(run())
