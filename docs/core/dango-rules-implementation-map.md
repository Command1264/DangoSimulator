# 小團快跑規則對映表

來源文件：`docs/core/dango-rules.md`

本表排除「結算與晉級說明」。應援獎勵、人氣值獎勵、黑馬值刷新與晉級流程不在本輪實作範圍。

## 流程說明

| 規則 | 對應元件 | 狀態 |
| --- | --- | --- |
| 每個賽程 21:00 開賽 | `RaceSupportWindow.race_starts_at` | 已實作 |
| 應援從前一賽程結束後開放 | `RaceSupportWindow.opens_at` | 已實作 |
| 應援於 20:30 關閉 | `RaceSupportWindow.closes_at` / `is_open()` | 已實作 |

## 移動與堆疊

| 規則 | 對應元件 | 狀態 |
| --- | --- | --- |
| 骰子隨機決定行動順序 | `RaceSimulator._start_round()` | 已實作，每輪洗牌一次 |
| 骰子決定前進步數 | `RaceSimulator._roll_for()` / `step_dango()` | 已實作 |
| 一般團子骰 1-3 | `RaceSimulator._roll_for()` | 已實作 |
| 終點格已有團子時疊到最上方 | `RaceSimulator._place_group()` | 已實作；布大王依專屬規則永遠在底部 |
| 任一一般參賽團子抵達終點即完成比賽 | `RaceSimulator._record_finishers()` | 已實作 |
| 名次依最靠近終點到最遠排序 | `RaceSimulator._live_rankings()` / `_ordered_by_progress()` | 已實作 |
| 同一格依堆疊由上至下排序 | `RaceSimulator._ordered_by_progress()` | 已實作，完賽名次與即時名次共用 |

## 技能與機制

| 規則 | 對應元件 | 狀態 |
| --- | --- | --- |
| 團子每輪行動時有機率發動技能 | `AbilityConfig.probability` / builtin ability handlers | 已實作 |
| 技能影響行動方式 | `before_move` / `after_move` / `round_start` / `on_device` triggers | 已實作 |
| 賽道存在阻礙或幫助前進的機關 | `DeviceType` / `RaceSimulator._apply_device()` | 已實作 |

## 賽道裝置

| 規則 | 對應元件 | 狀態 |
| --- | --- | --- |
| 推進裝置向前 1 格 | `DeviceType.ADVANCE` | 已實作 |
| 阻遏裝置向後 1 格 | `DeviceType.BLOCK` | 已實作 |
| 時空裂隙重排堆疊 | `DeviceType.TIME_RIFT` / `_open_time_rift()` | 已實作；一般團子隨機重排，布大王仍固定於底部 |

## 布大王

| 規則 | 對應元件 | 狀態 |
| --- | --- | --- |
| 第 1、2 回合一般團子先行動，第 3 回合開始從終點向起點移動 | `_can_act_in_round()` / `_forward_delta()` | 已實作 |
| 行動時賽道機制對布大王生效 | `_apply_device()` | 已實作 |
| 布大王骰 1-6 | `_roll_for()` | 已實作 |
| 推進/阻遏對布大王效果反轉 | `_apply_device()` | 已實作 |
| 永遠處於堆疊底部 | `_place_group()` / `_open_time_rift()` | 已實作；落點與時空裂隙後都會維持底部 |
| 行動時不帶走一般團子 | `_take_moving_group()` | 已實作 |
| 整輪結束後，若布大王前進方向到終點間已無一般團子，傳送回終點 | `should_boss_return_to_finish()` / `_finish_round()` / `_return_boss_to_finish()` | 已實作 |

## 團子技能

| 團子 | Ability id | 對應元件 | 狀態 |
| --- | --- | --- | --- |
| 西格莉卡 | `sigurd_sun_help` | `_apply_round_start_abilities()` | 已實作 |
| 弗洛洛 | `floro_bottom_bonus` | `_start_round()` / `_apply_builtin_before_move()` | 已實作；以回合開始時的底層快照判定 |
| 琳奈 | `linne_colorful` | `_apply_builtin_before_move()` / `step_dango()` | 已實作；無法移動時跳過移動、落點裝置與堆疊變動 |
| 守岸人 | `shorekeeper_future` | `_roll_for()` | 已實作 |
| 愛彌斯 | `aemiss_ghost` | `_apply_after_move_abilities()` | 已實作 |
| 緋雪 | `snow_bird` | `_update_boss_meeting_flags()` / `_apply_builtin_before_move()` | 已實作 |
| 陸赫斯 | `lu_device_master` | `_device_ability_delta()` | 已實作 |
| 達妮婭 | `daphne_same_roll_bonus` | `_apply_builtin_before_move()` | 已實作 |
| 卡提希婭 | `kat_activate_late_surge`, `kat_late_surge_bonus` | `_apply_after_move_abilities()` / `_apply_builtin_before_move()` | 已實作 |
| 菲比 | `phoebe_bonus` | `_apply_builtin_before_move()` | 已實作 |
| 千咲 | `chisaki_bonus` | `_apply_builtin_before_move()` | 已實作 |
| 珂萊塔 | `colletta_double_authority` | `_apply_builtin_before_move()` | 已實作 |

## 預設資料

`data/default_race.json` 預設勾選 A 組 6 顆一般團子與布大王干擾者。
文件列出的其它 WIP 團子也已加入資料檔，`default_selected=false`，因此 GUI 會顯示卡片但不會預設參賽。
