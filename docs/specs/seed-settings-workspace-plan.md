# Seed 設定搬移至設定頁實作計畫

## Summary

將 GUI 的 Seed 設定從多輪模擬工作區移到設定工作區，讓單輪模擬與多輪模擬共用同一組 Seed mode 與固定 Seed 輸入。此變更只調整 presentation layer，不改 core seed 解析規則與設定檔 schema。

## Goals

- 設定頁新增 `Seed 設定` 區塊。
- `Seed mode` 與 `固定 Seed` 輸入欄位只出現在設定頁。
- 單輪模擬 `configure_race_from_controls()` 與多輪模擬 `run_batch()` 都繼續使用同一組 Seed 控制。
- 固定 Seed / 系統隨機 Seed 行為不變：
  - 固定 Seed：使用輸入欄位值。
  - 系統隨機 Seed：使用系統隨機產生的 seed，且不覆寫固定 Seed 輸入欄位。
- 單輪或多輪模擬進行中，Seed 控制需禁用，避免執行中改變來源設定。

## Non-Goals

- 不修改 `settings.json` schema。
- 不新增單輪與多輪各自獨立的 Seed。
- 不改 `resolve_seed()`、`SeedMode` 或 CLI 行為。

## Implementation Tasks

1. 更新 GUI layout probe 測試：
   - Seed mode 與 fixed Seed input 的 parent/ancestor 必須位於 `settings_workspace`。
   - 多輪工作區 label 不應再包含 `Seed` 或 `固定 Seed：`。
   - 設定工作區 label 應包含 `Seed 設定` 與 `固定 Seed：`。
2. 調整 `dangosim/gui/app.py`：
   - 從 `_build_results_panel()` 移除 Seed mode、fixed Seed label 與 input。
   - 在 `_build_settings_workspace()` 建立同一組 `self.seed_mode`、`self.fixed_seed_label`、`self.seed_input`。
   - 保留 `selected_seed_mode()`、`fixed_seed_value()`、`apply_loaded_settings_to_controls()`、`current_user_settings()` 使用同一批 widget。
   - `apply_control_state()` 繼續依單輪/多輪執行狀態控制 Seed 欄位。
3. 更新文件：
   - `docs/specs/gui-dashboard-layout-design.md`
   - `docs/core/pre-release-manual-qa-checklist.md`
4. 驗證：
   - 先確認更新後測試在實作前失敗。
   - 實作後執行 GUI layout probe、system seed probe、全套 pytest、compileall、GUI smoke 與 `git diff --check`。

