# Git Workflow

本文件是 DangoSimulator 的 Git Flow source of truth。
`AGENTS.md` 保留強制摘要；本文件保留完整操作細節。

## Branch Model

本 repository 使用 Git Flow。

- `main`：stable release branch，只放可視為 release baseline 的狀態。
- `develop`：日常整合分支，也是 GitHub default branch。
- `codex/feature/<scope>`：一般功能、refactor、maintenance、非純文件變更。
- `codex/release/<version>`：release candidate stabilization。
- `codex/hotfix/<scope>`：從 `main` 開出的緊急修補。

## Default Starting Point

新任務開始時先執行只讀檢查：

```powershell
git status --short --branch
git branch --show-current
```

依目前分支決定操作：

- 在 `main`：不要直接做日常開發；先切到 `develop`，或從 `develop` 開 `codex/feature/<scope>`。
- 在 `develop`：純文件修改可直接提交；非純文件工作必須先開 `codex/feature/<scope>`。
- 在 `codex/feature/...`：只延續同一 coherent feature；不把不相關新工作疊上去。
- 在 `codex/release/...`：只做 stabilization、version、release notes 與 final verification。
- 在 `codex/hotfix/...`：只做緊急 production fix。

## Docs-Only Exception

純文件修改可以直接在 `develop` 上操作並提交。

純文件修改包含只修改：

- `docs/`
- `AGENTS.md`
- `SYSTEM.md`
- `README.md`
- checklist
- planning markdown

若同一任務同步修改 source code、tests、build config、runtime config、dependency files、package metadata 或輸出行為，則不再是 docs-only，必須從 `develop` 開 `codex/feature/<scope>`。

## Feature Flow

一般 implementation 流程：

```powershell
git switch develop
git pull --ff-only
git switch -c codex/feature/<scope>
```

完成後：

1. 執行相關 verification。
2. 只 stage 本次相關檔案。
3. 建立 conventional commit。
4. 若 remote operations 已授權，推送 working branch。
5. 等待使用者明確確認可以 merge。

未獲得明確 merge 許可前，不得 merge 回 `develop`。

## Merge-Back Flow

只有在使用者明確說「可以合併」、「merge 回去」、「OK 合併」或等價指示後，才執行 merge-back。

feature merge-back：

```powershell
git switch develop
git pull --ff-only
git merge --no-ff codex/feature/<scope>
```

merge 後：

1. 在 `develop` 執行必要 verification。
2. 推送 `develop`。
3. 若沒有保留理由，刪除已完成的 local working branch。
4. 若 remote operations 已授權，也刪除 remote working branch。

## Release Flow

release branch 從 `develop` 開出：

```powershell
git switch develop
git pull --ff-only
git switch -c codex/release/<version>
```

release branch 只允許：

- bug fix
- version update
- release notes
- final verification

使用者確認 release 可整合後：

1. merge 回 `main`。
2. 在 `main` 打 tag。
3. merge 回 `develop`。
4. 推送 `main`、`develop` 與 tag。
5. 刪除 release branch。

## Hotfix Flow

hotfix branch 從 `main` 開出：

```powershell
git switch main
git pull --ff-only
git switch -c codex/hotfix/<scope>
```

使用者確認 hotfix 可整合後：

1. merge 回 `main`。
2. 視需要打 patch tag。
3. merge 回 `develop`。
4. 推送 `main`、`develop` 與 tag。
5. 刪除 hotfix branch。

## Commit Rules

- 使用 conventional commits，例如 `feat:`, `fix:`, `docs:`, `test:`, `chore:`。
- 一個 commit 只包含一個 coherent、verified slice。
- 不把不相關修改包進同一個 commit。
- 若 commit 涉及行為、測試或 release 風險，body 應包含 test plan。
- verification 尚未通過時不要 commit。

## Remote Rules

- `origin` 指向公開 GitHub repository：`https://github.com/Command1264/DangoSimulator.git`。
- `develop` 是 GitHub default branch。
- remote push、branch delete、default branch 變更屬於有副作用操作；除非使用者已授權該 remote flow，否則先確認。
- 本 repository 已授權使用 GitHub remote 作為正常 Git Flow 收尾的一部分，但 merge-back 仍必須等待使用者明確確認。

## Current State

目前專案已建立：

- `main`
- `develop`
- `origin/main`
- `origin/develop`

後續日常工作以 `develop` 為起點。
