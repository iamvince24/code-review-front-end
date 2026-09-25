# code-review-front-end

審查 React / Next.js、Angular、AngularJS 的前端 diff 與 PR。只回報能指出具體失敗情境的問題，不把偏好當成缺陷。

授權是 [MIT](LICENSE)。

## 需求

- Python 3.9+
- git

腳本只用 Python 標準庫，不用另外安裝套件。

## 安裝

```bash
sh scripts/install.sh
```

會把這個目錄 symlink 到：

- `~/.cursor/skills/code-review-front-end`
- `~/.claude/skills/code-review-front-end`
- `~/.agents/skills/code-review-front-end`

目錄本身已經是其中一個時略過該路徑。目標已存在且不是 symlink 時不覆蓋。三個宿主都讀各自目錄裡的 `SKILL.md`。

## 使用

在要審查的 repo 裡，請 agent 做前端 code review。沒有指定 PR、分支或檔案時，它會審查目前分支與未提交改動。

可以指定：

- 模式：`standard` 或 `deep`。沒指定時，小 diff 走 `standard`；前端 diff 超過 500 行或 20 個檔案，或變更行碰到驗證、機密、HTML sink、Server Action、環境與部署設定時走 `deep`。
- 面向：`correctness`、`risk`、`maintainability`。
- 檢查：只有明確要求時才執行本機 ESLint 與 TypeScript compiler。

兩種模式都由主 session 審查；`deep` 會讀取更多呼叫端、設定與框架脈絡。

## 測試

```bash
python3 -m unittest discover -s scripts/tests
```
