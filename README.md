# DangoSimulator

DangoSimulator 是一個以 Python 與 PySide6 實作的《鳴潮》二週年「小團快跑」模擬器。專案重點是把賽跑規則、批次模擬、CLI 與 GUI 分層，讓核心模擬邏輯可以被測試、重現與打包。

## 專案重點

- 純 Python simulation core，GUI 與 CLI 共用同一套規則邏輯。
- JSON 可配置賽道、裝置、角色能力與公式。
- 支援 headless CLI，可輸出 JSON / CSV。
- 支援固定 seed 與系統隨機 seed，兼顧重現性與一般使用情境。
- 批次模擬支援多 worker，利用 CPU 多核心執行大量場次。
- 具備 pytest 測試與 Windows EXE 打包流程。

## 架構

```text
dangosim/core/     純 Python domain model、規則與 simulation engine
dangosim/cli/      headless CLI 與批次輸出
dangosim/gui/      PySide6 桌面 UI
data/              內建 JSON 範例資料
tests/             自動化測試
docs/              架構、規格、發行與 QA 文件
scripts/           開發環境與打包腳本
```

核心邊界：

- `dangosim/core` 不依賴 PySide6、pyqtgraph、PyInstaller 或 CLI。
- GUI 與 CLI 都透過 core public API 執行模擬。
- 批次模擬集中在 `dangosim.core.batch`，避免 GUI 與 CLI 各自重寫規則。

## 主要功能

### 規則與資料

- 以 JSON 定義賽道、裝置、角色能力與公式。
- 模擬核心與 UI 分離，方便測試與調整規則。
- 內建預設資料：[`data/default_race.json`](data/default_race.json)。

### CLI / Headless 模式

- 支援不開啟 GUI 的批次模擬。
- 可輸出 JSON / CSV，方便做後續統計或比較。
- 固定 seed 以 `base_seed + 場次索引` 派生每場 seed，使不同 worker 數下仍能產生一致統計。

### GUI

- 使用 PySide6 建立桌面操作介面。
- GUI 只負責互動、背景執行緒與狀態展示。
- 實際模擬與批次聚合由 core 層完成。

### 批次模擬

- 單 worker 模式保留逐場進度回報與取消檢查。
- 多 worker 模式使用 `ProcessPoolExecutor` 分 chunk 執行。
- `auto` worker 使用約 2/3 CPU core，`full` worker 使用目前全部 CPU core。
- 指定 worker 數會在 core 層限制到目前 CPU core 數，避免過度建立程序。

## 技術棧

- Python 3.12
- PySide6
- pyqtgraph
- pytest
- PyInstaller

## 開發環境

本專案使用專屬 `.venv`，並透過 Windows Python Launcher 固定 Python 版本：

```powershell
.\scripts\setup-dev.ps1
.\.venv\Scripts\python.exe -m pytest
```

GUI 與打包依賴較大，需要時再安裝：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
```

## 執行方式

CLI：

```powershell
.\.venv\Scripts\python.exe -m dangosim.cli.main --help
```

GUI：

```powershell
.\.venv\Scripts\python.exe -m dangosim.gui.app
```

## 測試

```powershell
.\.venv\Scripts\python.exe -m pytest
```

測試涵蓋 core race、abilities、batch simulation、CLI/data、GUI services/settings、packaging 等模組。

## 打包

Windows EXE 使用 PyInstaller 與 `DangoSimulator.spec`：

```powershell
.\scripts\build-exe.ps1
```

打包時需將 `data/` 一起納入，確保內建 JSON 設定可在 EXE 中讀取。

## 文件

- [專案總覽](docs/core/project-overview.md)
- [專案架構](docs/core/project-architecture.md)
- [規則文件](docs/core/dango-rules.md)
- [發行紀錄](docs/releases)

## 授權

本專案使用 MIT License 開源。
