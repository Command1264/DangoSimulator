# JSON 設定規格

## 目標

讓賽道、裝置、團子能力與應援公式都能由 JSON 設定，避免每次活動更新都必須修改程式碼。

## 安全規則

- 不允許 `eval`。
- 不允許 `exec`。
- 不允許以 JSON 指定任意 Python module 或 function。
- 僅允許白名單 action；目前已實作 `add_steps` 與 `builtin`。
- `builtin` 只會呼叫程式碼中明確支援的能力 id，不會從 JSON 執行任意 Python 程式碼。

## 驗證規則

- 格號必須在賽道範圍內。
- 裝置效果 type 必須是已知 enum。
- `track.devices` 可放 `type: "midpoint"` 作為賽程中點標記；它不是裝置效果，不會進入 `DeviceType`，可與同格推進、阻遏或時空裂隙並存。
- 若 `track.devices` 內有多個 `midpoint`，只採用第一個讀取到的標記。
- 團子 id 必須唯一。
- 起始位置必須合法。
- 能力 `id` 必須供程式碼與 JSON 規則引用。
- 能力 `name` 是 GUI 與事件紀錄顯示名稱；若舊 JSON 未提供，載入時會回退顯示 `id`。
- 未知能力 action 必須報錯。

## Ability Trigger 白名單

- `before_move`
- `after_move`
- `after_roll`
- `round_start`
- `on_device`

## Ability Action 白名單

- `add_steps`
- `builtin`
