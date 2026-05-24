# 團子設定彈窗版面修正計畫

## Summary

修正 `ParticipantSetupDialog` 在選擇大量團子時的版面問題，並改善團子卡片技能描述區的一致性。此變更只調整 PySide6 GUI 呈現，不改參賽資料、設定檔 schema 或 core 模擬規則。

## Root Cause

- 上方已選團子摘要 `count_label` 目前是一般 `QLabel`，長文字會參與橫向 size hint，可能把彈窗寬度撐大。
- 團子技能描述目前是每張卡片獨立 label，雖然已置中與換行，但沒有按 grid row 統一高度；同一排卡片在技能長度不同時容易高度不齊。

## Design

- 已選團子摘要：
  - 啟用 word wrap。
  - 設定水平 size policy 為 `Ignored`，讓它依目前 UI 寬度換行，而不是要求更寬的彈窗。
  - 保持位於標題下方。
- 技能描述框：
  - 每張卡片保留一個 `skill_note_label`。
  - 文字上下左右置中。
  - 使用固定邊框/背景讓它成為明確描述框。
  - 以每一排為單位，將該排所有技能描述框高度設定為該排最高者。

## Recommendation

採用「每排同高」而不是「全彈窗所有卡片同高」。原因是全域同高會被單一超長技能拉高所有卡片，降低可視密度；每排同高能保留整齊欄位，也避免不必要的空白。

## Test Plan

- 新增 GUI probe 測試：
  - 摘要 label 啟用換行。
  - 摘要 label 不使用會撐寬彈窗的水平 size policy。
  - 每排技能描述框高度一致。
  - 技能描述框文字為水平/垂直置中。
- 執行全套 pytest、compileall、GUI smoke 與 `git diff --check`。

