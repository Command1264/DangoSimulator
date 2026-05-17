# Pre-release Manual QA Checklist

## GUI

- [ ] 可啟動 PySide6 GUI。
- [ ] 可載入預設小組賽資料。
- [ ] 可在左側卡片勾選一般團子參賽。
- [ ] 可將布大王切換為干擾者或參賽者。
- [ ] 可執行單場模擬並看到事件紀錄。
- [ ] 點「下一步」後中央賽道、骰子、名次與事件紀錄會更新。
- [ ] 自動播放可暫停與重置。
- [ ] 可執行批次模擬並看到勝率摘要。
- [ ] 固定 seed 連跑兩次同設定會得到相同批次結果。
- [ ] 系統隨機 seed 會顯示並回填本次實際使用 seed。
- [ ] 批次結果表顯示勝場、勝率、平均名次與綜合分數。
- [ ] JSON 錯誤會顯示可理解訊息。

## CLI

- [ ] `dangosim simulate` 可讀取預設資料。
- [ ] 固定 seed 的輸出可重現。
- [ ] 系統隨機 seed 的 JSON/CSV 輸出包含本次實際使用 seed。
- [ ] 可輸出 JSON。
- [ ] 可輸出 CSV。

## Packaging

- [ ] Windows EXE 可啟動。
- [ ] EXE 可找到內建 `data/`。
- [ ] EXE 可完成一次 headless 模擬。
