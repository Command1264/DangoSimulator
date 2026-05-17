# 專案架構

## 分層

- `dangosim/core/`：純 Python domain 與 simulation engine。
- `dangosim/cli/`：headless 批次模擬。
- `dangosim/gui/`：PySide6 桌面 UI。
- `data/`：內建 JSON 範例資料。
- `tests/`：自動化測試。
- `scripts/`：開發環境與打包腳本。

## 邊界

`dangosim/core` 不依賴 PySide6、pyqtgraph、PyInstaller 或 CLI。
GUI 與 CLI 都必須透過 core 的 public API 執行模擬，不能各自重寫賽跑規則。

批次模擬集中在 `dangosim.core.batch`：

- 單 worker 模式保留逐場進度回報與取消檢查。
- 多 worker 模式使用 `ProcessPoolExecutor` 分 chunk 執行，以利用 CPU 多核心。
- 固定 seed 以 `base_seed + 場次索引` 派生每場 seed，因此同一批設定在不同 worker 數下仍需產生一致統計。
- GUI 只負責背景執行緒與狀態展示；實際批次聚合由 core 完成。

## Python 版本

專案使用 `.python-version` 指定 Python 3.12，並用 Windows Python Launcher 建立 `.venv`：

```powershell
py -3.12 -m venv .venv
```

實際使用時執行：

```powershell
.\scripts\setup-dev.ps1
```

## 依賴策略

- `requirements-dev.txt`：最小開發與測試依賴。
- `requirements-gui.txt`：GUI 與打包依賴，只有需要跑 GUI 或打包時安裝。
- `pyproject.toml`：套件 metadata、console script 與 pytest 設定。

## 打包

Windows EXE 使用 PyInstaller 與 `DangoSimulator.spec`。
內建 `data/` 必須透過 `datas=[("data", "data")]` 一起打包。
