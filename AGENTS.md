# DangoSimulator Agent Guide

先讀 `SYSTEM.md`，那裡定義通用操作規則。
本檔補充 DangoSimulator 專案專屬規則。

關鍵共用規則：在任何建立、修改、刪除檔案，或執行有副作用的命令之前，先提出計畫並等待使用者明確確認；若使用者已明確要求實作同一份方案，視為該方案範圍已確認。

## Canonical Project Rule File

這份檔案是此 repository 的 canonical、team-shared project instruction file。
通用 agent 行為定義在 `SYSTEM.md`。
如果還有其他 agent-specific 檔案，請把本檔視為 project source of truth，而其他檔案只作為相容性 wrapper。

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

## Engineering Workflow

對 non-trivial 工作：

1. 在修改前先形成簡短計畫。
2. 優先採 test-first 或 test-with-change flow。
3. 以 incremental、可 review 的方式修改。
4. 完成前執行相關檢查。
5. 當行為、架構、GUI 流程或 release 風險改變時，同輪更新文件與手動 QA checklist。

一般開發規則：

- 優先使用 immutability 與 explicit state transitions。
- 避免 hidden side effects。
- 驗證所有 external input boundaries。
- 明確處理 errors。
- 不要吞掉 exceptions。
- 保持檔案聚焦且模組化。
- 新增或修改程式碼時，必須為非顯而易懂的規則、狀態轉換、相容性處理或設計取捨，加上簡潔註解說明為什麼。
- 不要替每行程式碼或自明邏輯加機械式註解。
- 建立 commit message 時遵守 conventional commits。

## Git Workflow

完整細節見 `docs/core/git-workflow.md`；本節是強制摘要。

Git 是 mandatory workflow，不是等使用者提醒才做的項目。
只要任務改動 code 或 tracked docs，除非使用者明確阻止，agent 應主動處理 local git flow。

Branch model：

- 本 repository 使用 Git Flow，兩條 long-lived branches：
  - `main` 是 stable release branch。
  - `develop` 是日常整合的預設分支。
- 不要直接在 `main` 或 `develop` 上持續做 non-trivial implementation work。
- working branch prefix 必須是 `codex/`。

Branch rules：

- `codex/feature/<scope>` 從 `develop` 開出。
- 除非更適合 release 或 hotfix 類型，否則新功能、refactor、docs、maintenance 都使用 `codex/feature/<scope>`。
- 純文件修改可以直接在 `develop` 上操作並提交，不一定要開新的 feature branch。
- 純文件修改包含只修改 `docs/`、`AGENTS.md`、`SYSTEM.md`、`README`、checklist 或 planning markdown，且沒有同步修改 source code、test、build config、runtime config 或 package metadata。
- 若文件修改伴隨任何 code、config、dependency、runtime behavior 變更，仍視為一般 feature work，必須從 `develop` 開 `codex/feature/<scope>`。
- `codex/release/<version>` 從 `develop` 開出，只用於 release candidate stabilization。
- `codex/hotfix/<scope>` 從 `main` 開出，只用於緊急修補已發布狀態。

Merge-back rules：

- 當 `codex/feature/...` branch 完成 coherent、verified slice，agent 應先 commit 並視 remote 授權狀態推送 working branch。
- 只有在使用者明確確認可以合併後，才 merge 回 `develop`。
- 使用者沒有明確說可以合併時，不可把沒有阻止解讀成允許 merge。
- 不要把下一個不相關 feature 疊在已完成但尚未 merge 的 feature branch 上。
- 每次 feature merge 後，下一個工作應從最新的 `develop` 重新開 branch。
- feature、release、hotfix branch 已成功 merge 且沒有保留理由時，應主動刪除已完成的 working branch；若 remote operations 已授權，也應刪除 remote branch。

Commit rules：

- 完成一個 coherent、verified slice 後，stage 相關檔案並建立 conventional commit。
- 不要把不相關工作包進同一個 commit。
- 若有幫助，commit body 中要附上具體 test plan。
- 如果工作仍在探索中，或 verification 尚未通過，就不要先 commit。

Current project branch classification：

- 目前專案狀態：greenfield MVP foundation，且已切換到 Git Flow 管理。
- `main` 是穩定 release baseline。
- `develop` 是後續工作的主整合線，也是 GitHub default branch。
- 新工作通常應從 `develop` 開 `codex/feature/...`。
- `codex/release/...` 保留給 release preparation，`codex/hotfix/...` 保留給緊急 production fix。

## AI-Agent Working Rules

- 遵守 `SYSTEM.md` 中的通用 approval 與 execution 規則。
- 在 non-trivial implementation 前，先檢查 `git status` 與目前分支。
- 如果目前分支是 `main`，先切到 `develop` 或從 `develop` 開正確的 `codex/...` working branch，再開始寫碼。
- 如果目前分支是 `develop`，只有 docs-only 工作可直接提交；其他工作先開 `codex/feature/<scope>`。
- 如果目前 feature branch 已完成且驗證通過，但使用者尚未明確確認可以合併，先 commit / push working branch 並停止在等待確認狀態。
- verification 通過後，不要等提醒，直接 commit 已完成的 slice。
- 若本輪任務有修改使用者可見 GUI、CLI、輸出格式、錯誤處理、packaging 或 release 風險，必須檢查並更新 `docs/core/pre-release-manual-qa-checklist.md`。
- 每次完成一個已驗證的 implementation slice 後，final response 應附上一小段建議手動測試清單。

## Task-Specific Docs

- `docs/core/git-workflow.md`：Git Flow、branch、merge-back、remote 與 default branch 規則。
- `docs/core/pre-release-manual-qa-checklist.md`：上架前的人類手動驗收 source of truth。
- `docs/core/dango-rules.md`：使用者整理的小團快跑規則來源。
- `docs/core/dango-rules-implementation-map.md`：規則到程式元件與測試覆蓋的對映表。
- `docs/specs/gui-dashboard-layout-design.md`：GUI 儀表板、單場展示、多輪模擬與 seed 顯示設計。
- `docs/specs/race-engine-spec.md`：核心賽跑規則與模擬引擎規格。
- `docs/specs/json-config-spec.md`：JSON 賽道、裝置、團子與能力設定規格。
- `docs/specs/betting-system-spec.md`：應援與黑馬值系統規格。
