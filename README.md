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
