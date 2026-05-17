# Pre-release Manual QA Checklist

## GUI

- [ ] 可啟動 PySide6 GUI。
- [ ] 可載入預設小組賽資料。
- [ ] 可執行單場模擬並看到事件紀錄。
- [ ] 可執行批次模擬並看到勝率摘要。
- [ ] JSON 錯誤會顯示可理解訊息。

## CLI

- [ ] `dangosim simulate` 可讀取預設資料。
- [ ] 固定 seed 的輸出可重現。
- [ ] 可輸出 JSON。
- [ ] 可輸出 CSV。

## Packaging

- [ ] Windows EXE 可啟動。
- [ ] EXE 可找到內建 `data/`。
- [ ] EXE 可完成一次 headless 模擬。
