# DangoSimulator Agent Guide

先讀 `SYSTEM.md`，那裡定義通用操作規則。
本檔補充 DangoSimulator 專案專屬規則。

關鍵共用規則：在任何建立、修改、刪除檔案，或執行有副作用的命令之前，先提出計畫並等待使用者明確確認；若使用者已明確要求實作同一份方案，視為該方案範圍已確認。

## Project Summary

DangoSimulator 是一個 Python + PySide6 的《鳴潮》二週年「小團快跑」桌面模擬器。

近期目標：

- 規則精準的純 Python 模擬核心。
- JSON 可配置賽道、裝置、團子能力與應援公式。
- PySide6 GUI 與 headless CLI 共用同一套核心。
- 支援大量模擬與 Windows EXE 打包。

## Current Delivery Stage

專案目前是 early greenfield bootstrap。
新增檔案時優先建立清楚的 architecture separation，而不是快速堆在單一檔案。

MVP priorities：

- 小團快跑核心規則引擎。
- 可載入 JSON 的賽道、裝置、團子與能力設定。
- 布大王特殊逆向規則。
- 批次模擬與結果匯出。
- 最小可用 PySide6 GUI。
- 繁體中文文件與手動 QA checklist。

第一階段非目標：

- 官方帳號登入或網路同步。
- 自動抓取官方活動資料。
- 完整遊戲畫面復刻。
- 任意 Python 外掛能力執行。
- 未確認官方公式的硬編碼應援結算。

## Domain Rules

目前規則來源：

- 巴哈姆特 2026 小團快跑規則整理：https://forum.gamer.com.tw/C.php?bsn=74934&snA=16806
- 錦標賽活動資訊：https://news.17173.com/content/05092026/151142498.shtml
- TapTap 活動預告：https://www.taptap.cn/moment/801779883398136340
- 既有網頁版模擬器參考：https://dumpling-run2.vercel.app/

已知核心規則：

- 一般團子順時針跑。
- 每回合先隨機決定行動順序，再擲骰子移動。
- 一般團子基礎骰為 1 到 3。
- 團子落到同格時，後到者堆疊在先到者上方。
- 底部團子移動時會帶動其上方整個堆疊。
- 裝置在移動終點落格時觸發。
- 推進裝置讓團子向前 1 格。
- 阻遏裝置讓團子向後 1 格。
- 時空裂隙會重排該格堆疊順序。
- 布大王預設逆時針、骰 1 到 6，且推進/阻遏裝置效果反轉。

若官方資料與社群資料衝突，將該規則設為可配置，並在文件中標記來源與假設。

## Architecture Rules

目標架構：

- `dangosim/core/`：純 Python domain 與 simulation engine，不依賴 GUI。
- `dangosim/gui/`：PySide6 presentation layer。
- `dangosim/cli/`：headless simulation command。
- `data/`：內建 JSON 範例與預設資料。
- `docs/core/`：專案治理、架構、工作流、QA。
- `docs/specs/`：功能規格與設計決策。
- `tests/`：單元與 CLI 測試。

必要邊界：

- core 不 import PySide6、pyqtgraph 或任何 GUI package。
- GUI 不重新實作賽跑規則，只呼叫 core。
- CLI 與 GUI 使用同一套 JSON loader 與 simulator。
- JSON 能力系統不得使用 `eval`、`exec` 或任意可執行字串。
- 所有外部輸入 JSON 必須驗證，錯誤要回報明確原因。

## Data Design Rules

資料檔需保持人類可讀、可 diff：

- 使用 UTF-8。
- 使用穩定 key 排序。
- 優先使用明確 enum 字串，例如 `advance`、`block`、`time_rift`。
- 未知欄位不得默默吞掉；要回報或保留在明確的 `metadata`。
- 預設資料與使用者自訂資料分離，避免升級時覆蓋使用者設定。

## Testing Expectations

- 核心規則必須有單元測試。
- 新增能力或裝置前先寫測試。
- 固定 seed 的模擬結果應可重現。
- JSON loader 必須測非法輸入與錯誤訊息。
- CLI 至少測 JSON 輸出與 CSV 輸出。
- GUI 先用 smoke/manual QA checklist 驗證；核心邏輯不得只靠 GUI 手測。

## Packaging Expectations

- 打包目標是 Windows EXE。
- PyInstaller spec 必須包含 `data/` 預設資料與必要資源。
- 程式內資源路徑必須同時支援原始碼執行與 PyInstaller frozen mode。
- EXE 驗收至少包含啟動 GUI、載入預設資料、執行一次 headless 模擬。

## Documentation Rules

- 行為或架構改變時，同輪更新文件。
- 規格文件放 `docs/specs/`。
- 核心流程與手動驗收放 `docs/core/`。
- 文件使用繁體中文。
- 若仍是推測規則，必須明確標記為假設，不得寫成官方事實。
