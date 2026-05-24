# 上方工作區導覽實作計畫

## Summary

將目前主視窗左側工作區導覽改為上方 tab 導覽，讓 `單輪模擬` 工作區可以使用完整水平寬度，地圖更接近畫面中央。此變更只調整 GUI shell，不改單輪、多輪、設定頁內部邏輯。

## Design

- 主視窗外層改為垂直排列：
  - 上方：`QTabBar`，顯示 `單輪模擬`、`多輪模擬`、`設定`。
  - 下方：既有 `QStackedWidget`。
- 保留既有 attribute 名稱：
  - `workspace_nav`
  - `workspace_stack`
- `workspace_nav.currentChanged` 連動 `workspace_stack.setCurrentIndex`。
- 第一個 tab 預設選中 `單輪模擬`。
- 原本各工作區 objectName 不變，避免既有 probe 與 GUI 邏輯大改。

## Test Plan

- 更新 layout probe：
  - `workspace_nav_widget_class == "QTabBar"`。
  - `workspace_shell_layout == "vertical"`。
  - `workspace_nav_items == ["單輪模擬", "多輪模擬", "設定"]`。
  - `workspace_stack_pages` 不變。
- 執行相關 GUI layout probe、全套 pytest、compileall、GUI smoke、`git diff --check`。

