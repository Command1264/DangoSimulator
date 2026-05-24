# GUI 工作區重整實作計畫

## Summary

將目前單一 dashboard 重整成三個一般使用者導向的工作區：`單輪模擬`、`多輪模擬`、`設定`。第一版目標不是重寫 GUI，而是在現有 `MainWindow` 內加入左側導覽與 `QStackedWidget`，把既有單輪流程、多輪流程與參賽設定入口拆到清楚的頁面。

## Goals

- 使用者可從左側導覽切換 `單輪模擬`、`多輪模擬`、`設定`。
- `單輪模擬` 專注顯示賽道、即時名次、本輪行動、事件紀錄與單場控制。
- `多輪模擬` 專注顯示場數、Seed、CPU worker、進度、ETA 與結果表。
- `設定` 顯示目前參賽團子摘要，並保留「自訂參賽團子」卡片彈窗入口；第一版不把整個卡片 dialog 內嵌到頁面。
- 既有 user settings、單輪模擬、多輪 worker、seed 行為、按鈕啟用規則都維持。
- GUI smoke/layout probe 測試更新為新結構。

## Non-Goals

- 不重寫 `ParticipantSetupDialog` 成完整內嵌設定頁。
- 不新增賽道/裝置 GUI 編輯器。
- 不改 core 模擬規則。
- 不更動設定 JSON schema。

## Target Layout

```text
┌──────────────────────────────────────────────────────────────┐
│ DangoSimulator 小團快跑模擬器                                │
├──────────────┬───────────────────────────────────────────────┤
│ 單輪模擬      │                                               │
│ 多輪模擬      │ QStackedWidget active workspace               │
│ 設定          │                                               │
│              │                                               │
└──────────────┴───────────────────────────────────────────────┘
```

## Workspace Details

### 單輪模擬

- Object name：`single_race_workspace`
- 內容：
  - 左側：參賽摘要與事件紀錄。
  - 中央：標題、賽道、單場控制、骰子/seed 顯示。
  - 右側：即時名次與本輪行動。
- 沿用既有 `_build_left_panel()`、`_build_center_panel()`、`_build_right_panel()`，外層改為 workspace widget。

### 多輪模擬

- Object name：`batch_simulation_workspace`
- 內容：
  - 上方：場數、Seed mode、固定 Seed、CPU worker、排序、執行/停止。
  - 中間：進度條與 ETA。
  - 下方：結果表，至少保留 7 列高度。
- 沿用既有 `_build_results_panel()` 的 controls、progress、results table，但外層不再是主畫面下方 split group。

### 設定

- Object name：`settings_workspace`
- 內容：
  - 參賽團子摘要。
  - `自訂參賽團子` 按鈕。
  - 全域 Seed 設定。
  - 作者與版本號。
- 設定頁只展示團子、Seed 與關於資訊；速度、場數、CPU worker、結果排序等操作性設定留在各自工作區，避免設定頁變成重複控制面板。

## Implementation Tasks

### Task 1: Add Workspace Layout Probe Tests

**Files**

- Modify: `tests/test_gui_packaging.py`

**Steps**

- 新增/更新 `test_gui_dashboard_layout_places_events_under_participants_and_aligns_tables`，讓 probe 期待：
  - `workspace_nav_items == ["單輪模擬", "多輪模擬", "設定"]`
  - `workspace_stack_pages == ["single_race_workspace", "batch_simulation_workspace", "settings_workspace"]`
  - `event_log_parent == "left_panel"`
  - `result_table_parent == "batch_simulation_workspace"`
  - 既有 table alignment 仍一致。
- 先跑該測試，預期失敗，因目前尚無 workspace nav/stack。

### Task 2: Build MainWindow Shell With Navigation

**Files**

- Modify: `dangosim/gui/app.py`

**Steps**

- 匯入 `QStackedWidget`。
- 在 `MainWindow.__init__()` 建立：
  - `self.workspace_nav = QListWidget()`
  - `self.workspace_stack = QStackedWidget()`
- 新增 `_build_shell()`，回傳包含左側導覽與右側 stack 的 root widget。
- 新增 `_build_single_race_workspace()`，把目前 `single_race_group` 內的水平 splitter 搬進單輪頁。
- 新增 `_build_batch_workspace()`，包裝既有 `_build_results_panel()` 回傳內容。
- 新增 `_build_settings_workspace()`，提供設定摘要與參賽設定入口。
- 導覽切換使用 `currentRowChanged.connect(self.workspace_stack.setCurrentIndex)`。

### Task 3: Keep Controls And State Rules Working Across Workspaces

**Files**

- Modify: `dangosim/gui/app.py`

**Steps**

- 保留既有 attribute 名稱：`start_button`、`run_batch_button`、`events`、`results` 等，避免 worker 與 smoke probes 大改。
- `apply_control_state()` 繼續控制同一批 widget。
- `set_participant_controls_enabled()` 同時控制左側/設定頁的參賽設定入口。
- 新增 `refresh_settings_summary()`，在 `persist_user_settings()`、`refresh_selected_summary()`、`apply_loaded_settings_to_controls()` 後更新設定頁摘要。
- `open_participant_setup()` 成功後仍呼叫 `refresh_selected_summary()`、`persist_user_settings()`、必要時 `reset_race()`。

### Task 4: Update GUI Probe Output

**Files**

- Modify: `dangosim/gui/app.py`
- Modify: `tests/test_gui_packaging.py`

**Steps**

- 更新 `DANGOSIM_GUI_LAYOUT_PROBE` 輸出：
  - `workspace_nav_items`
  - `workspace_stack_pages`
  - `active_workspace`
  - `result_table_parent`
- 移除舊的 `root_splitter_widgets == ["single_race_group", "batch_simulation_group"]` 期待。
- 保留 `window_maximized`、alignment、visible rows、event log parent 檢查。

### Task 5: Documentation And Manual QA

**Files**

- Modify: `docs/specs/gui-dashboard-layout-design.md`
- Modify: `docs/core/pre-release-manual-qa-checklist.md`

**Steps**

- 記錄主視窗改為左側導覽 + 三工作區。
- QA 增加：
  - 可在三個工作區間切換。
  - 單輪模擬頁能完整跑單場。
  - 多輪模擬頁能執行 1000 場並顯示進度/ETA/結果。
  - 設定頁能開啟參賽團子卡片視窗並保存設定。

### Task 6: Verification And Commit

**Commands**

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_gui_packaging.py::test_gui_dashboard_layout_places_events_under_participants_and_aligns_tables -q
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m compileall dangosim
$env:DANGOSIM_GUI_SMOKE='1'; .\.venv\Scripts\python.exe -m dangosim.gui.app
git diff --check
```

**Expected Result**

- 所有測試通過。
- GUI smoke 正常結束。
- 沒有 whitespace error。

## Rollout Notes

- 這是 v0.3.0 等級的 GUI 架構重整候選，不應混入 core 規則修正。
- 若第一版完成後使用者希望設定頁可以直接內嵌團子卡片，再另開第二階段計畫。
