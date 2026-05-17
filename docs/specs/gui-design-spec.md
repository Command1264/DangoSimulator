# GUI 設計規格

## 目標

提供繁體中文 PySide6 桌面介面，讓使用者可以載入賽道與團子設定、跑單場模擬、執行大量勝率模擬，後續再擴充視覺化賽道編輯器。

## MVP 畫面

- 標題：`DangoSimulator 小團快跑模擬器`
- 載入內建 `data/default_race.json`
- 顯示參賽團子數量
- 按鈕：跑單場
- 按鈕：計算勝率
- 批次模擬場數輸入：1 到 100000
- 結果區：文字顯示排名或 JSON 勝率摘要

## 後續擴充

- `QGraphicsView/QGraphicsScene` 圓形賽道動畫。
- JSON 設定編輯器。
- 裝置與能力表單。
- pyqtgraph 勝率與平均名次圖表。
- 錯誤面板顯示 JSON 驗證失敗原因。

## 邊界

GUI 不直接修改 core 狀態內部欄位。
所有模擬都應建立 `RaceSimulator` 或呼叫 CLI 共用的 `simulate_many`。
