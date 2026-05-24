# 設定工作區集中控制實作計畫

## Summary

將團子設定入口集中到 `設定` 工作區，讓 `單輪模擬` 與 `多輪模擬` 工作區只負責執行與展示。Seed 設定與團子設定都視為全域賽前設定；任一模擬流程啟動後都不可修改。單輪比賽完賽後，GUI 應回到可直接按「開始」開新一場的狀態。

## Goals

- 團子設定只出現在 `設定` 工作區。
- `單輪模擬` 左側只保留事件紀錄，不再顯示參賽團子設定入口。
- `設定` 工作區保留目前參賽團子摘要與 `自訂參賽團子` 按鈕。
- 單輪模擬或多輪模擬啟動中：
  - Seed mode 禁用。
  - 固定 Seed 輸入禁用。
  - 自訂參賽團子按鈕禁用。
- 單輪比賽一結束：
  - 停止自動播放。
  - 單輪模擬狀態改為非執行中。
  - `開始` 按鈕重新啟用，可直接開始下一場。

## Non-Goals

- 不改參賽團子彈窗內部卡片設計。
- 不改使用者設定檔 schema。
- 不改 core 比賽完賽規則。

## Implementation Tasks

1. 更新 GUI layout/control probe 測試：
   - `自訂參賽團子` 只位於 `settings_workspace`。
   - `left_panel` 不再有 `參賽團子` label 或設定按鈕。
   - 單輪啟動後 Seed 與團子設定禁用。
   - 單輪完賽後 `開始` 重新啟用。
2. 調整 `dangosim/gui/app.py`：
   - 從 `_build_left_panel()` 移除參賽摘要與設定按鈕。
   - `refresh_selected_summary()` 只更新設定頁摘要。
   - `set_participant_controls_enabled()` 只控制設定頁按鈕。
   - `step_race()` 在 `state.finished` 時將 `single_race_active` 設為 `False` 並套用控制狀態。
3. 更新 GUI 規格與手動 QA checklist。
4. 驗證：
   - 目標 GUI layout probe。
   - system seed probe。
   - 全套 pytest。
   - compileall、GUI smoke、`git diff --check`。

