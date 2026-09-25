# code-review-front-end

Cursor skill，審查 React / Next.js、Angular、AngularJS 的前端 diff 與 PR。只回報能指出具體失敗情境的問題，不把偏好當成缺陷。

授權是 [MIT](LICENSE)。

## 需求

- Cursor
- Python 3.9+
- git

腳本只用 Python 標準庫，不用另外安裝套件。

## 安裝

### Cursor Plugin

這個 repo 根目錄有 `.cursor-plugin/plugin.json`。裝成 plugin 時，根目錄的 `SKILL.md` 與 `agents/` 裡的三個 reviewer 會一起載入，不必再跑安裝腳本。

官方公開列表要等審核。作者送出後，從 Cursor Marketplace 搜尋 `code-review-front-end` 安裝。送審頁：[cursor.com/marketplace/publish](https://cursor.com/marketplace/publish)。

Cursor Teams / Enterprise 可以直接匯入這個 GitHub repo：

`https://github.com/iamvince24/code-review-front-end`

### 手動安裝

```bash
git clone https://github.com/iamvince24/code-review-front-end.git ~/.cursor/skills/code-review-front-end
bash ~/.cursor/skills/code-review-front-end/scripts/install_agents.sh
```

`install_agents.sh` 會把三個 reviewer symlink 到 `~/.cursor/agents/`。deep 模式才會派這些 agent。

## 使用

在要審查的 repo 裡，請 Cursor 做前端 code review。沒有指定 PR、分支或檔案時，它會審查目前分支與未提交改動。

可以指定：

- 模式：`standard` 或 `deep`。沒指定時，小 diff 走 `standard`；前端 diff 超過 500 行或 20 個檔案，或碰到驗證、機密、HTML sink、Server Action、部署設定時走 `deep`。
- 面向：`correctness`、`risk`、`maintainability`。
- 預設模式：`python3 <skill>/scripts/profile_repos.py config <repo> --mode standard|deep`

`standard` 由主 session 自己審查。`deep` 最多派出 `fe-review-correctness`、`fe-review-risk`、`fe-review-maintainability`。

## 測試

```bash
python3 -m unittest discover -s scripts/tests
```

## 設計筆記

[doc/](doc/) 是這個 skill 的設計筆記，不是使用手冊。現行行為以 [SKILL.md](SKILL.md) 為準。
