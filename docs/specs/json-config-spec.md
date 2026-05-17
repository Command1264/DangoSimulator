# JSON 設定規格

## 目標

讓賽道、裝置、團子能力與應援公式都能由 JSON 設定，避免每次活動更新都必須修改程式碼。

## 安全規則

- 不允許 `eval`。
- 不允許 `exec`。
- 不允許以 JSON 指定任意 Python module 或 function。
- 僅允許白名單 action，例如 `move`, `mark`, `teleport`, `shuffle_stack`, `set_state`。

## 驗證規則

- 格號必須在賽道範圍內。
- 裝置 type 必須是已知 enum。
- 團子 id 必須唯一。
- 起始位置必須合法。
- 未知能力 action 必須報錯。
