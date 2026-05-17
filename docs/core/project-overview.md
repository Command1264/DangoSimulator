# 專案總覽

DangoSimulator 是《鳴潮》二週年「小團快跑」模擬器。

第一版聚焦：

- 規則精準。
- 資料可擴充。
- 可大量模擬。
- 可打包 Windows EXE。
- 專屬 `.venv` 與 Python 3.12 版本控制。

核心設計是讓 GUI、CLI、測試都共用同一套 `dangosim.core`，避免畫面邏輯與規則邏輯分裂。
