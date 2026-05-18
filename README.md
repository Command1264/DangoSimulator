# DangoSimulator

DangoSimulator 是一個以 Python 與 PySide6 實作的《鳴潮》二週年「小團快跑」模擬器。

第一版目標：

- 規則精準的純 Python 模擬核心。
- JSON 可配置賽道、裝置、團子能力與應援公式。
- PySide6 GUI 與 headless CLI 共用同一套核心。
- 支援 Windows EXE 打包。

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

## 隨機種子

CLI 與 GUI 支援兩種 seed 模式：

- 固定 seed：可輸入 0 到 2^64-1 的整數，並重現模擬結果。
- 系統隨機 seed：使用 Python `secrets.randbits(64)` 產生本次 seed，GUI 會在目前 seed 顯示區顯示實際使用 seed，但不覆寫固定 Seed 輸入欄位；CLI JSON/CSV 輸出會記錄實際 seed。

Python 會透過作業系統安全隨機來源取得 entropy；標準函式庫不保證直接使用 CPU 熱噪聲。

## 授權

本專案使用 MIT License 開源。
