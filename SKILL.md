---
name: code-review-front-end
description: Review frontend diffs and PRs for React/Next.js, Angular, and AngularJS. Use for frontend code review requests involving JavaScript, TypeScript, templates, styles, or frontend configuration. Do not use for implementation-only requests that do not ask for review.
---

# 前端 Code Review

審查使用者指定的 PR、分支或檔案；沒有指定時審查目前分支與未提交改動。只回報能指出具體失敗情境的問題，不把偏好當成缺陷。

## 準備資料

先取得 skill 的絕對路徑，再執行：

```bash
python3 <skill>/scripts/prepare_diff.py prepare --repo <repo>
```

可加上：

- `--base <ref> --head <ref>`：審查分支或 PR。
- `--mode standard|deep`：明確指定模式；明確指定時優先於自動判斷。
- `--focus correctness,risk,maintainability`：只檢查指定面向。
- `--spec <path>`：使用者主動提供 Spec 時才傳入；不要詢問 Spec。
- `--checks`：只有使用者要求執行檢查時才加入，會執行本機 ESLint 與 TypeScript compiler。

指令會回傳資料包路徑、模式、原因、diff、context、lint 與 typecheck 狀態。`status: empty` 時直接回報沒有前端改動。

## 審查

主 session 讀 `context.json`、`diff.patch` 與 [review checklist](references/review-checklist.md)，只讀 context 列出的 review root，自行完成審查，不派子 agent。

- `standard`：一般規模且沒有高風險訊號。
- `deep`：使用者明確指定、前端 diff 超過 500 行或 20 個檔案，或變更行涉及驗證／授權、機密、HTML sink、Server Action／Route Handler、環境與部署設定。需要框架細節時讀 [framework notes](references/framework-notes.md)，並檢查完整函式、呼叫端與受影響設定。

只檢查 context 的 `focus`。critical／high finding 必須重新查看對應程式碼，確認失敗情境與影響後才列入報告。

## 輸出

依序輸出：

1. `結論`：不建議合併／修完再合併／可以合併。
2. findings：依 critical、high、medium、low 排序；每筆包含變更檔案與行號、問題、影響與建議。
3. lint 與 typecheck 的實際狀態；未執行時說明未執行，不推測結果。
4. 未完成或無法確認的範圍；沒有就省略。

沒有 findings 時用一小段文字說明可以合併與執行過的檢查，不輸出空白風險模板。不要詢問或執行修正；後續修正是新的修改請求。

## 收尾

若 prepare 建立了資料包，最後一定執行：

```bash
python3 <skill>/scripts/prepare_diff.py cleanup --dir <dir> --token <token>
```
