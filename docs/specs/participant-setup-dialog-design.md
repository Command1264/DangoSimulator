# 參賽團子設定彈窗規劃

## 目標

將主畫面左側的參賽團子清單改為摘要與「自訂參賽團子」按鈕，讓一般使用者透過彈出式視窗完成參賽團子、初始位置、初始堆疊順序與首回合順序設定，不需要操作 JSON 或 Python code。

## 使用者流程

1. 使用者在主畫面按下「自訂參賽團子」。
2. 系統開啟 `ParticipantSetupDialog`，顯示所有內建團子卡片。
3. 使用者點擊卡片本體切換是否上場。
4. 被選取的卡片可編輯：
   - 初始位置。
   - 初始堆疊順序。
   - 首回合順序。
   - 布大王模式。
5. 使用者按「確認」後才套用設定並寫入使用者 config。
6. 使用者按「取消」或關閉視窗時，不套用本次變更。

## 主畫面變更

- 左側只保留：
  - `參賽團子` 標題。
  - 已選團子摘要。
  - `自訂參賽團子` 按鈕。
- 單輪或多輪模擬進行中，`自訂參賽團子` 按鈕停用。
- 主畫面不再直接顯示完整團子卡片清單。

## Dialog 版面

- 上方：
  - 標題：`自訂參賽團子`。
  - 副標：顯示目前選取數量，例如 `已選 8 顆`。
  - 地圖下拉選單先保留在 UI 規格中，第一版可只顯示目前預設地圖並停用。
- 中央：
  - `QScrollArea` 包住 `QGridLayout`。
  - 每張團子卡片固定寬度，預設每列 4 張。
  - 不顯示橫向卷軸；內容以垂直卷軸瀏覽。
  - 卡片整張可點擊，行為等同大型 checkbox，但不顯示 checkbox 方框。
  - 選取卡片使用明顯邊框與淡色背景；未選取卡片降低透明感，且編輯欄位停用。
  - 卡片內所有數字輸入與下拉選單不攔截滑鼠滾輪；滾輪事件交由外層卷軸處理。
- 下方：
  - `確認`。
  - `取消`。

## 卡片內容

- 團子 avatar：
  - 第一版使用團子名稱第一個可見字。
  - 未來可改接圖片資源。
- 團子 avatar 與名稱採上下排列，並在卡片中置中顯示。
- `group` 顯示：
  - 若 JSON 有 group，就在卡片左上角以圓形或橢圓形 badge 顯示。
  - 不顯示 WIP 類狀態標籤。
- 初始位置：
  - `QSpinBox`，範圍為 `1..track.length`。
- 初始堆疊順序：
  - `QComboBox`，第一個選項為 `隨機`。
  - 其餘選項使用數字，數字越小越靠底部；只在多顆團子初始位置相同時影響結果。
  - 未指定者仍使用 seed 隨機補入。
- 首回合順序：
  - `QComboBox`，第一個選項為 `隨機`。
  - 其餘選項使用數字，數字越小越早行動。
  - 只影響第一回合；第二回合後仍使用目前每輪亂序規則。
  - 布大王仍遵守第 3 回合才行動，因此首回合設定不會讓布大王提前行動。
- 初始堆疊順序與首回合順序在卡片底部並排顯示，降低卡片高度並方便對照。
- 布大王模式：
  - `干擾者`。
  - `參賽者`。

## 選取數量

- 不限制可選團子數量。
- 仍至少需要 1 顆一般團子，否則確認時顯示錯誤並不關閉 Dialog。
- 已選數量只作為摘要，不阻止使用者繼續選取。

## 資料模型

`ParticipantCardState` 增加：

- `start_position: int`
- `initial_stack_order: int | None`
- `first_round_order: int | None`

`ParticipantSettings` 增加：

- `participant_overrides: tuple[ParticipantOverrideSettings, ...]`

`ParticipantOverrideSettings` 欄位：

- `dango_id`
- `selected`
- `start_position`
- `initial_stack_order`
- `first_round_order`

舊 config 若沒有 override，載入時沿用原本 `selected_dango_ids`、團子 JSON 的 `start_position`，堆疊與首回合維持隨機。

## Core 規則

`RaceConfig` 增加：

- `initial_stack_order: Mapping[str, int]`
- `first_round_order: Mapping[str, int]`

`RaceSimulator` 初始化時：

- 先建立同格 stack。
- 若該格有指定 `initial_stack_order`，指定者依數字由小到大排在底部到頂部。
- 未指定者保留 seed 隨機順序並補入。
- 布大王仍固定維持底部。

`RaceSimulator._start_round()`：

- 第一回合先依 seed 產生完整亂序。
- 若 `first_round_order` 有設定，指定者依數字由小到大排在前方。
- 未指定者保留 seed 亂序補入。
- 第二回合後照既有每輪亂序。
- 布大王的第 3 回合限制優先於首回合設定。

## 測試計畫

- view model：
  - 卡片保留 group。
  - 卡片可儲存初始位置、初始堆疊順序、首回合順序。
  - 建立 `RaceConfig` 時會套用選取、起始格與 order overrides。
- settings：
  - 新格式可 round-trip。
  - 舊格式可載入。
  - 非法位置與非法 order 會回退為安全值。
- core：
  - 預設初始堆疊仍 seed 隨機。
  - 指定初始堆疊順序時可重現。
  - 首回合順序只影響第一回合。
  - 布大王不會因首回合設定提前行動。
- GUI smoke：
  - 主視窗可開啟 dialog。
  - 取消不套用。
  - 確認會更新摘要與設定。
