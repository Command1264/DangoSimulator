# 多輪結果表 Header 排序實作計畫

## Summary

將多輪模擬結果排序從下拉選單改為直接點擊結果表 header。排序支援降冪、升冪、不使用此欄排序三態；預設使用綜合分數降冪。排名欄只顯示目前排序後的視覺排名，不可作為排序依據。

## Requirements

- 多輪結果表可直接點 header 排序。
- 排名欄不可排序。
- 預設排序為 `綜合分數` 降冪。
- 點同一個可排序欄位循環：
  - 降冪。
  - 升冪。
  - 不使用此欄排序。
- 若某欄進入「不使用此欄排序」，回到預設 `綜合分數` 降冪，確保表格永遠有穩定排序。
- 排名欄顯示需反映目前排序方向：
  - 降冪排序時顯示 `1..N`。
  - 升冪排序時顯示 `N..1`。
- Header 顯示排序狀態，例如 `勝率 ▼`、`勝率 ▲`。

## Design

- 移除多輪控制列中的「排序」下拉選單，避免和 header 排序產生兩套來源。
- 保留設定檔中的 `sort_mode` 欄位作相容欄位；載入舊設定時不報錯，儲存時以目前 header 排序欄位名稱回填。
- `MainWindow` 新增：
  - `batch_result_rows`：保存最近一次多輪結果原始 rows。
  - `batch_sort_column`：目前排序欄位，預設 `weighted_score`。
  - `batch_sort_direction`：目前方向，預設 `desc`。
- Header click handler：
  - 忽略排名欄。
  - 點新欄位時設為該欄降冪。
  - 點同欄時依 `desc -> asc -> default` 循環。
- `render_results()` 只更新原始資料與 seed/progress，再呼叫 `render_result_rows()`。
- `render_result_rows()` 根據目前排序狀態排序並重畫表格。

## Test Plan

- GUI probe：
  - 預設結果使用綜合分數降冪。
  - 點勝率 header 後改為勝率降冪，排名顯示 `1..N`。
  - 再點勝率 header 後改為勝率升冪，排名顯示 `N..1`。
  - 第三次點勝率 header 回到預設綜合分數降冪。
  - 點排名 header 不改變排序狀態。
- 全套 pytest、compileall、GUI smoke、`git diff --check`。

