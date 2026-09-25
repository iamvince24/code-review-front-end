# code-review-front-end 優化建議 v2

> 日期：2026-09-25
> 依據：v1（`doc/optimization-review.md`）＋外部建議的「AI Code Review Agent Skill 六層架構」（薄入口、按需載入 references、確定性驗證、findings 格式、雜訊控制、eval）
> 對照的現況：`git log` 到 `ad540bb`（C4 完成）
> 這份報告只做分析與決策點，沒有改任何程式碼。
> 進度（2026-09-25）：D2 已完成（`3aeabe3`）。試跑 baseline 時發現並修正兩個問題（`cc2b1f7`、`a254870`，見 D1）。**所有「先量測」的項目暫緩**：eval 一輪要 4–5 小時，改成實際用來 code review 時依回饋調整，見[第 7 節](#7-暫緩的量測項目與實際使用的回饋紀錄)。

## 0. 結論

這個 skill 的形狀**已經和建議架構一致**：`SKILL.md` 負責流程、`plan` 用 script 決定每個審查員讀哪些 references（這比讓 LLM 自己挑更可靠）、`aggregate` 用確定性規則驗證與彙整、有 eval 框架。所以 v2 **不需要重組架構**，缺口集中在三個地方：

1. **eval 從沒跑過**。C4 的 `evals/run.py` 已經可以批次跑，但 `evals/results/` 還不存在。之後所有會改變輸出的項目（包括 v1 的 A6 合併）都卡在這裡。（**暫緩**：成本太高，改用實際使用的回饋，見第 7 節。）
2. **雜訊控制只在 subagent 端做，彙整端沒擋**。`aggregate` 不看 `confidence`，也沒有最低嚴重度門檻；`high` 強度下未驗證的 `confidence: low` / `medium` findings 會直接進報告。而 `score.py` 只把高於 `max_other_severity`（多半是 `medium`）的 findings 算成誤報，**medium 以下的雜訊量不到**。
3. **eval 只有正例和「乾淨」的案例，沒有「安全反例」**。21 個案例中 19 個是「應該抓到」、2 個是「不應該有 findings」，沒有「看起來像、其實安全」的案例，精準度等於沒量。

建議架構中有幾點**不適用或應該延後**，理由見第 4 節：改成單一 agent 加按需 references（要等 A6 的數據）、把 `SKILL.md` 的步驟放寬（那些步驟是 script 的串接，不是判斷）、新增 testing 審查員、把 invariant 改放到 `AGENTS.md`。

---

## 1. v1 的狀態校正

v1 的「進度」寫到 A1 / A6 工具 / B6 部分完成，但 git 紀錄已經往前推了：

| 項目 | v1 寫的 | 實際（git） |
|---|---|---|
| A4 `min_level` | 未動 | ✅ `fcccb6d`：`reviewers.json` 改成 `min_level`，必跑的審查員必須從 `low` 開始 |
| B6 agent 檔與安裝 | 部分完成（只有 `git init`） | ✅ `6ae3248`：`agents/` 納入 skill、`scripts/install_agents.sh`、`plan` 輸出 `missing_agents`、`test_agents.py` 檢查 frontmatter |
| C4 eval 自動化 | 未動 | ✅ `d2011b7` + `ad540bb`：`FE_REVIEW_HOME` 隔離狀態、`--no-spec`、`evals/run.py`（`--runs`、`--parallel`、`--skip`）、`score.py --compare` |
| A6 | 工具完成、未跑分 | 不變：**仍未跑分** |

仍未處理：A2、A3 / C1、A5、B1、B4、B5、B7、C5、C6、C7。

另外一個小問題：`SKILL.md` 第 2 步寫「只改到後端時建議改用 `/code-review`」，但目前環境中沒有叫 `code-review` 的 skill（`~/.cursor/skills/` 只有這個 skill 和 `open-knowledge-discovery`），這會導向一個不存在的入口。

---

## 2. 六層對照

| 層 | 建議 | 目前的實作 | 缺口 | 判斷 |
|---|---|---|---|---|
| 1. repo 層級的 invariant | `AGENTS.md` 放架構邊界、相容性保證、資料邊界 | `REVIEW.md`（從**比較基準**讀，PR 無法放寬自己的規則）＋個人備註＋`AGENTS.md` 只當慣例資料 | `setup.md` 引導大家寫「嚴重度重新定義、小建議上限」，沒有引導寫 invariant；只讀根目錄一份 | 機制比建議好，**內容引導不夠** → D5、D8 |
| 2. `SKILL.md` = workflow / router | 短、只寫流程、指向 references | 187 行、11.7KB，全是流程；references 由 `plan` 分配，主 session 不讀 | 只在特定情況才用到的分支（`--since-last` 缺口處理、Spec 詢問、inline、PR 平台）每次都載入；強度數字重複（A5） | 大致符合 → D9（小幅） |
| 3. 按需載入的 domain references | 依 diff 類型只讀相關的 | `reviewers.json` 的 `refs` + `framework_part`，`auto_skip` 依 diff 內容略過角度 | 無結構性缺口。部分清單項目和 ESLint 規則重疊 | 已做到 → D7 |
| 4. 確定性驗證 | lint、test、typecheck、script | lint（只在工作目錄模式）、diff 行號（C2）、欄位驗證（B3）、彙整（B2） | 沒有 `tsc`（C6）；PR 模式沒有 lint（C5）；沒有 test；`evidence` 無法驗證 | **最薄的一層** → D7、D10 |
| 5. 雜訊控制 | severity 門檻、confidence、上限、忽略路徑 | 每人上限、報告上限、verifier 門檻、`low` / `medium` 準確優先、`EXCLUDES` / `.cursorignore` | 彙整端**沒有** severity 門檻與 confidence 過濾 | **主要缺口** → D3 |
| 6. eval | 每條規則測「應該觸發 / 安全反例 / 無關變更」 | 21 個案例、角度歸屬、skip 變體、`--compare` | 沒跑過；沒有安全反例；medium 以下的雜訊不計分；`REVIEW.md` 規則只有正例 | **主要缺口** → D1、D2、D4 |

建議架構的 finding 格式（severity / location / problem / evidence / impact / suggestion / rule）和目前的協定對照：

| 建議欄位 | 目前 | 差異 |
|---|---|---|
| severity | `severity` + `confidence` | 已有，而且多了 confidence |
| location | `file` + `line` + `side` | 已有，C2 之後行號可靠 |
| problem | `summary` | 已有 |
| impact | `failure_scenario` | 已有 |
| suggestion | `suggestion` | 已有 |
| evidence | 無（`related_locations` 語意是「同一根本原因的其他位置」，不是證據） | → D10 |
| rule | 無 | → D6 |

---

## 3. v2 新增項目

編號用 D，避免和 v1 的 A / B / C 混淆。

### D1. 先跑 baseline（P0）

**狀態：暫緩（2026-09-25）。**試跑過，但完整一輪太花時間，改成依實際使用的回饋調整（第 7 節）。

#### 試跑紀錄

- **成本**：單一案例在 `high` 強度要 10–14 分鐘（8 個子審查員 + verifier）。21 × 3 = 63 次、`--parallel 3`，估計 4–5 小時。
- **發現一：新版 `cursor-agent`（2026.09.23）在 headless 模式只讀 workspace 的 `.cursor/agents/`，不讀 `~/.cursor/agents/`**（放真正的檔案也一樣）。派 `fe-review-*` 會得到 `Invalid enum value`，主 session 沒有照 `SKILL.md` 退回 inline，而是自行改派一般子審查員。已修正 eval 端：`make_repo.py` 把 `agents/` 複製到每個案例 repo 並寫進 `.git/info/exclude`；`run.py` 認得 `{"custom": {"name": …}}` 形式的 `subagentType`，且只計 `started` 事件（`cc2b1f7`）。實際使用端的影響見 D11。
- **發現二：子審查員把 category 當成 angle 回傳**（naming → `ai-readability`、types → `type-safety`），`aggregate` 查不到允許的 category，就把 category 改成 `other`。已修正：`aggregate` 依 `reviewers.json` 對回 key，派工訊息加上 `key：`，協定寫明 `angle` 照抄 key（`a254870`）。這個 bug 在實際使用中也會發生，不只影響 eval。
- **尚未驗證**：兩個修正之後還沒有完整跑過一次 skill，只有單元測試（200 個）通過。

---

**為什麼**：建議架構和 v1 的共同前提都是「先量測、再調整」。C4 已經把批次執行做好，現在只差跑。D3、D4、D7 和 A6 的每一項都會改變輸出，沒有 baseline 就無法判斷是變好還是變差。

**做法**：

```bash
cd ~/.cursor/skills/code-review-front-end
python3 evals/run.py /tmp/fe-eval-baseline --model <模型> --label baseline --runs 3 --parallel 3
```

- 21 案例 × 3 次 = 63 次，每次都派子審查員（`--no-inline`）。
- 結果寫到 `evals/results/<日期>-baseline.json`，之後每一項改動都用 `score.py --compare` 對照。
- **建議先做 D2 再跑**：D2 只改評分，不改 skill 的行為，但會讓 baseline 多記錄雜訊。要是先跑再改 D2，就得用 `logs/` 重新評分（`score.py` 讀的是輸出 JSON，所以可以重算，不用重跑）。

`evals/results/` 要不要進 git：建議要。它是之後所有決策的依據，而且一次只有幾 KB。

### D2. 評分要量得到雜訊（P0）

**狀態：已完成（2026-09-25）。**

#### 落地狀況

- `score_case` 新增 `listed`、`noise`（任何嚴重度的非預期 findings）、`other_items`、`noise_angles`。`false_positives`（高於 `max_other_severity`）與 `others` 的意義不變，`noise = false_positives + others`。
- `totals` 新增 `listed`、`noise`、`precision`（抓到 / 列出）、`noise_per_run`（雜訊 / 有輸出的次數）。
- 角度歸屬每個角度多一個 `noise`。行為改變：只碰到位置、沒有命中的角度，以前不會出現在角度表，現在會以雜訊列入。
- `--compare` 新增 `precision`、`noise_per_run` 的前後值，以及 `angle_noise`（各角度雜訊的變化）。D2 之前存的結果沒有這些欄位，前值顯示為 `—`。
- 文字輸出：每個案例列出「其他：`file:line severity [角度] summary`」供人工檢視；總計行加上精準度與雜訊/次；角度表加上「雜訊」「雜訊/次」兩欄。
- 測試：`test_evals.py`、`test_run.py` 更新，全部 198 個測試通過。

---

**現況**（完成前）

```72:77:evals/score.py
    limit = SEVERITY[case["max_other_severity"]]
    others = [f for i, f in enumerate(findings) if i not in used]
    false_pos = [f for f in others if SEVERITY.get(f.get("severity"), 0) > limit]
    return {"case": case["name"], "ran": report is not None, "expected": len(case["expect"]),
            "found": sum(r["found"] for r in results), "underrated": sum(r.get("underrated", False) for r in results),
            "false_positives": len(false_pos), "others": len(others) - len(false_pos),
```

幾乎每個案例的 `max_other_severity` 都是 `medium`，所以只有 high / critical 的非預期 findings 算誤報。一份報告附帶 8 筆 medium 的「可以抽成 hook」「命名可以更好」，分數和一份乾淨的報告相同。`others` 雖然有印出來，但沒有進 `--compare`，也沒有歸屬到角度。

**為什麼有問題**：建議架構的第 5 層（雜訊控制）要能驗證，前提是雜訊量得到。D3 會直接改變 medium / low 的輸出量，現在的評分看不出 D3 的效果。

**做法**：

```python
# score_case 的回傳加上
"listed": len(findings),
"noise": len(others),                                # 任何嚴重度的非預期 findings
"noise_angles": [angles_of(f) for f in others],
```

```python
# 彙總
precision = found / listed if listed else None       # 報告中有多少比例是真的問題
noise_per_run = noise / ran
```

- `--compare` 加上 `precision` 與 `noise_per_run` 的差異。
- 角度歸屬表加一欄「雜訊/次」，A6 的判斷標準從「誤報/次 > 1」改成同時看「雜訊/次」。
- 保留原本的 `false_positives`（高嚴重度誤報），它代表「會擋 PR 的誤報」，比雜訊嚴重得多，要分開看。

注意：`noise` 裡也會有「真的問題但案例沒預期」的 findings（案例是人工寫的小 repo，可能真的有別的毛病）。第一輪跑完要人工看一次 `noise` 清單，確認是雜訊還是案例本身的問題。

### D3. 彙整端的雜訊門檻（P1，依實際使用的回饋決定）

**狀態：未做。**原本要等 D1 的前後對照，D1 暫緩後改成：實際使用時雜訊明顯（第 7 節的「低嚴重度或低把握的 findings 大多不修」）就直接做，Q1 選 A。

**現況**

- 協定在 `high` / `max` 要求子審查員「不要在心裡先刪掉半信半疑的候選，用 `confidence` 表達把握程度」。這個設計是對的：把判斷留到彙整端，而不是讓每個審查員各自過濾。
- 但彙整端沒有接住：`aggregate.py` 只在合併時看 `confidence`，排序、截斷、列出都不看。verifier 在 `high` 只驗 critical / high。
- 結果：`high` 強度下，`confidence: low` 的 medium / low findings 沒有經過任何過濾就進報告，最多 15 筆。

**為什麼有問題**：召回優先的意思應該是「子審查員多提、彙整端嚴格篩」。現在是「子審查員多提、彙整端照單全收」，雜訊的來源正是這裡。

**做法**：在 `reviewers.json` 的強度設定中加入兩個欄位（順便解決 A5，數字集中到一處）：

```json
"level_config": {
  "low":    {"per_reviewer_cap": 3, "report_cap": 6,  "verify_min": null,     "list_min_severity": "medium", "unverified_min_confidence": "high"},
  "medium": {"per_reviewer_cap": 5, "report_cap": 6,  "verify_min": null,     "list_min_severity": "medium", "unverified_min_confidence": "high"},
  "high":   {"per_reviewer_cap": 5, "report_cap": 15, "verify_min": "high",   "list_min_severity": "medium", "unverified_min_confidence": "medium"},
  "max":    {"per_reviewer_cap": 8, "report_cap": 15, "verify_min": "medium", "list_min_severity": "low",    "unverified_min_confidence": "low"}
}
```

`aggregate.py` 在 `sort_findings` 之前加一段：

```python
def passes_gate(f, cfg):
    if _sev_rank(f["severity"]) > _sev_rank(cfg["list_min_severity"]):
        return False
    if f.get("verdict") in ("CONFIRMED", "PLAUSIBLE"):
        return True
    return CONF_RANK[f["confidence"]] <= CONF_RANK[cfg["unverified_min_confidence"]]

gated = [f for f in work if not passes_gate(f, cfg)]
work = [f for f in work if passes_gate(f, cfg)]
# gated 計入 truncated["gated"] 與 by_severity，報告寫「另有 N 筆低嚴重度或低把握的建議未列出」
```

- `low` / `medium` 本來就要求子審查員只報 `confidence: high`，這裡等於在彙整端再確認一次。
- `max` 維持「全部列出」，給需要看全部候選的時候用。
- stats 的 `listed` 會跟著下降，`raw ≥ deduped ≥ listed` 的不等式不受影響。

決策點見第 5 節 Q1。

### D4. eval 補上安全反例與無關變更（P1）

**狀態：暫緩（2026-09-25）。**寫案例本身不貴，但沒有跑 eval 就沒有用處。實際使用時遇到的誤報，記下來當成之後的反例來源（第 7 節）。

**為什麼**：建議架構的第 6 層要求每條規則都測三種情況。目前只有第一種（應該觸發）和一種很弱的第三種（`clean-refactor`、`clean-rename`）。雜訊主要出現在「看起來像問題」的程式碼上，只有安全反例能量到。

**做法**：每個正例配一個安全反例，`expect: []`、`max_other_severity: "low"`。`cases.py` 現有格式就支援，不用改 `make_repo.py`。

| 正例 | 安全反例 | 測的是 |
|---|---|---|
| `falsy-zero-render` | `{items.length > 0 && <List />}`，或 `isOpen && …`（`isOpen: boolean`） | correctness 會不會對每個 `&&` 都報 |
| `xss-html` | `dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }}` | security 會不會只看關鍵字 |
| `open-redirect` | `returnUrl` 先經過 `isSafePath()`（只允許 `/` 開頭且不是 `//`） | security 會不會追到防護函式 |
| `server-action-no-auth` | action 第一行 `await requireAdmin()`，實作在 `lib/auth.ts` | security 會不會讀 diff 外的防護 |
| `effect-no-cleanup` | `useEffect` 有回傳 cleanup | correctness |
| `angular-subscribe-leak` | `.pipe(takeUntilDestroyed(this.destroyRef))` 或 `async` pipe | Angular 清單是否只比對 `subscribe(` |
| `context-rerender` | `value` 用 `useMemo` 包起來 | architecture |
| `unsafe-json-cast` | `UserSchema.parse(JSON.parse(raw))`（zod） | types |
| `misleading-name` | `getUser()` 真的只讀取，只是回傳 `null` | naming 會不會對每個 `get*` 起疑 |
| `reimplement-util` | 在元件裡 import 並使用既有的 `formatCurrency` | codebase |
| `review-md-rule` | 中文字串在 `*.test.tsx`、或透過 `t('orders.save')` 取用 | `REVIEW.md` 規則會不會過度套用 |
| `breaking-prop-rename` | prop 改名，且 `Catalog.tsx` 也在同一個 diff 中改掉 | risk 會不會只看改名本身 |

無關變更（測 `auto_skip` 與「角度不該發言」）：

| 案例 | 內容 | 預期 |
|---|---|---|
| `css-only` | 只改 `.module.css` 的顏色與間距 | `expect: []`；types、state 被 `auto_skip`；a11y 可以發言但不應超過 low |
| `copy-change` | 只改按鈕文字（無 `REVIEW.md`） | `expect: []` |
| `test-only` | 只新增 `*.test.tsx` | `expect: []`；`EXCLUDES` 目前沒有排除 test 檔，所以會進審查範圍，這個案例測的是各角度會不會對測試程式碼套用正式程式碼的標準 |

規模：12 + 3 = 15 個新案例，總數 36。`--runs 3` 是 108 次，成本加倍。建議分兩批：先加 security 與 correctness 的 5 個反例（必跑角度、雜訊影響最大），確認 D2 的雜訊指標可用之後再補其他的。

### D5. `REVIEW.md` 的內容引導：從風格規則改成 invariant（P2）

**現況**：`setup.md` 建議 `REVIEW.md` 寫「嚴重度的重新定義、不審查的路徑、這個 repo 特有的檢查項目、小建議的數量上限」。eval 的 `review-md-rule` 用的規則是「寫死中文字串為 high」，這是 i18n lint 可以做的事。

**為什麼有問題**：`REVIEW.md` 是這個 skill 裡唯一可以讓團隊加入「只看 diff 看不出來的知識」的地方。建議架構的說法是：formatter、style、機械性檢查交給 CI，repo 層級的審查規則用來回答「reviewer 原本要靠經驗判斷的問題」。這個判斷準則是對的，不論出處。

**做法**：新增 `references/review-md-guide.md`（`setup` 時提示，不給子審查員讀），附一份範本：

```markdown
# 審查規則

## 相容性介面（改了要當成破壞性變更）
- `localStorage` key 以 `app:` 開頭的都是跨版本資料，改名或改格式為 high，除非同一個 PR 有遷移邏輯
- `lib/analytics/events.ts` 的事件名稱已經接到報表，不能改名或刪除
- `components/shared/` 的 props 是其他團隊在用的 API：移除或改名為 high

## 資料邊界
- 身分證字號、手機、email 不能出現在 URL query、`console.*`、analytics payload
- `NEXT_PUBLIC_*` 只能放公開值；新增時在 PR 描述說明為什麼可以公開

## 架構邊界
- `app/**` 的元件不直接 import `lib/api/client.ts`，一律透過 `hooks/queries/*`
- `features/a` 不 import `features/b` 的內部檔案，只能用各 feature 的 `index.ts`

## 不審查
- `legacy/**`：凍結中，只修 critical

## 不要寫在這裡
- 排版、import 順序、命名風格 → ESLint / Prettier
```

- 每一條都寫「長期不變的結果」，不寫函式名稱這類容易過時的實作細節。
- 每新增一條，就在 eval 加一組正例和反例（D4 的 `review-md-rule` 那一對就是範本）。
- `review-md-rule` 案例的規則可以換成上面的 `localStorage` 規則，更能代表「diff 看不出來」這類規則的價值。這是可選的：換掉的話，舊分數就不能直接比。

### D6. 規則歸屬：checklist 加穩定 ID、finding 加 `rule`（P2，推測有價值）

**為什麼**：建議架構的 eval 以「規則」為單位（這條規則的精準度多少），目前的 eval 和 stats 最細只到「角度」。要是某個角度誤報多，現在無法知道是哪幾條清單項目造成的，只能整個角度降級。

**做法**：

1. checklist 的每一條加上穩定 ID（檔名前綴 + 短名），例如 `security.md` 中：

   ```markdown
   - **[SEC-html]** `dangerouslySetInnerHTML`、`innerHTML` 搭配外部內容……
   - **[SEC-redirect]** `returnUrl` / `redirect` 造成開放重導……
   ```

2. 協定的 finding 加一個選填欄位：`"rule": "SEC-html"`；依 `REVIEW.md` 回報時填 `"REVIEW.md#相容性介面"`。
3. `aggregate` 驗證格式（`^[A-Z]+-[a-z0-9-]+$` 或 `REVIEW.md#…`），不合法就移除這個欄位，不丟棄整筆。
4. `score.py` 加上「依 rule 統計命中與雜訊」。

**成本與風險**：約 20 個 reference 檔要加 ID；LLM 填 `rule` 的一致性不確定（**推測**：會有一部分填錯或不填）。所以只做成選填，也不影響 finding 是否有效。建議等實際使用的紀錄（第 7 節）顯示某個角度的雜訊需要細分時再做。

### D7. 確定性驗證補強（P1）

建議架構的原則「能確定性檢查的就不讓 LLM 猜」，對應到三件事：

**D7-1. 把 C6（`tsc`）提前**（✅ 已完成：`prepare_diff.py typecheck`，serenity-canvas 實測 6 秒）。v1 把它放在 P2「其他」，但它是這一層投資報酬最高的項目：`tsc` 能百分之百確定的型別錯誤，types 審查員現在要用 5 筆額度去猜。做法照 v1 的 C6。

**D7-2. checklist 標出 ESLint 已經涵蓋的項目**。下列清單項目都有對應的常見 ESLint 規則：

| 清單項目 | 所在檔 | 對應規則 |
|---|---|---|
| `parseInt` 沒給 radix | `correctness.md`、`inline-checklist.md` | `radix` |
| `==` 的隱含轉換 | 同上 | `eqeqeq` |
| `<button>` 沒寫 `type` | 同上 | `react/button-has-type` |
| Promise 沒有 `catch`、`forEach` 裡的 `async` | 同上 | `@typescript-eslint/no-floating-promises`、`no-misused-promises` |
| 新增的 `any`、`@ts-ignore`、`!` | `types.md` | `@typescript-eslint/no-explicit-any`、`ban-ts-comment`、`no-non-null-assertion` |
| `<div onClick>`、圖片沒有 `alt`、input 沒有 label | `a11y.md` | `jsx-a11y/click-events-have-key-events`、`no-static-element-interactions`、`alt-text`、`label-has-associated-control` |
| `useEffect` / `useMemo` / `useCallback` 依賴缺漏 | `nextjs/correctness.md` 第 40 行 | `react-hooks/exhaustive-deps` |

目前協定寫「`lint.json` 已經列出的問題不要再回報」，但這只擋得住「lint 有跑而且真的報了」的情況。規則有啟用、這次沒報，代表程式碼沒問題，審查員還是會照清單再檢查一次。

做法：

```python
# lint 子指令：對第一個變更的 .tsx/.ts 檔跑一次
eslint --print-config <file>   # 取出 rules 中不是 "off" / 0 的 key
```

- 寫進 `context.md` 的「已啟用的 lint 規則」段落。
- 清單項目後面標 `〔eslint: radix〕`。協定加一句：「標了 eslint 規則、而且該規則在已啟用清單中的項目，跳過不檢查」。
- PR 模式（lint 不跑）時沒有這個段落，清單照常使用。這正好和 C5 互補：C5 做不成的話，至少工作目錄模式可以省 token。

**推測**：省下的 token 有限（每個角度的清單只有幾條會被跳過），主要收益是「子審查員的 5 筆額度不會被 lint 等級的問題佔掉」。D1 暫緩後，改看實際使用時這類 findings 是否常出現（第 7 節），太少就不做。

**D7-3. test 不做成審查員**。建議架構列了 `testing.md`，但對前端 PR，「缺少測試」這類 finding 幾乎都是雜訊，而且在 PR 模式下跑被審查分支的測試等於執行不受信任的程式碼（和 C5 的 lint 顧慮相同）。如果要做，只做工作目錄模式的選用旗標 `--run-tests`（`vitest related` / `jest --findRelatedTests`），失敗的測試寫進 `context.md` 當成已知事實。優先度 P3。

### D8. 依路徑套用的規則（P2）

**現況**：只讀比較基準根目錄的 `REVIEW.md`，上限 8KB。

**為什麼**：monorepo 裡 `packages/admin` 和 `packages/storefront` 的相容性介面、資料邊界完全不同，全部寫在根目錄的 `REVIEW.md` 會讓每次審查都載入無關規則，也容易超過 8KB。

**做法**：

- `plan` 對每個變更檔，從比較基準讀取「根目錄到該檔所在目錄」路徑上的每一份 `REVIEW.md`，去重後依深度排序寫進 `context.md`，每段標出適用範圍（`packages/admin/**`）。
- 總量仍然限制 8KB，超過時優先保留根目錄與變更檔最多的目錄。
- 分批（shard）時，每批只帶該批檔案適用的規則段落。

選用：沒有 `REVIEW.md` 時，讀比較基準 `AGENTS.md` 中 `## Review guidelines`（或 `## 審查規則`）這一節，放在同一個優先順序（協定的第 2 點）。其他段落維持「只當慣例資料」。好處是團隊只需要維護一份檔案；風險是 `AGENTS.md` 的其他段落會混進來，所以只取那一節。決策點見 Q4。

### D9. `SKILL.md` 的按需載入（P2，小幅）

`SKILL.md` 本身已經是流程，不是知識庫，不需要大改。能做的只有：

1. **只在特定分支才需要的內容移出**：`--since-last` 的缺口處理（第 3 步第一點）、Spec 詢問（第 3 步第三點）、inline 模式整段、之後 B4 要加的 PR 平台判斷。移到 `references/modes.md`，`SKILL.md` 留一行「遇到 X 時讀 Y」。預估從 11.7KB 降到 8–9KB。
2. **強度表格改成引用 `plan` 的輸出**（A5 的一部分；D3 把數字集中到 `reviewers.json` 之後自然完成）。
3. **修正 description 與 `/code-review` 的引導**（`/code-review` 引導已修正：改成告知不在審查範圍）：description 寫了「即使沒有明確說『前端』」，觸發範圍很廣。環境中沒有其他 review skill，現在不會互相搶，但第 2 步引導到不存在的 `/code-review`。改成「只改到後端時告知不在這個 skill 的範圍」，或改成實際存在的入口。

收益不大，排在 C7、D11、C6、B1 之後。

### D10. finding 加 `evidence`，並由 script 驗證（P2）

**為什麼**：建議的 finding 格式有 `evidence`，目前沒有。重點不是多一個欄位，而是**多一個可以用 script 驗證的東西**：LLM 最常見的誤報之一，是聲稱「呼叫端沒有處理」「API 會回傳 null」，卻沒有實際讀過那個位置。

**做法**：

```json
"evidence": ["app/catalog/Catalog.tsx:31", "lib/api/products.ts:12"]
```

- 選填，最多 3 個，格式同 `related_locations`。語意是「支持這個判斷、你實際讀過的位置」，和「同一根本原因的其他位置」分開。
- `aggregate` 驗證：檔案存在於審查根目錄、行號在檔案範圍內。不合法的條目移除，移除後如果 `evidence` 變成空的、而且 `failure_scenario` 提到其他檔案，`confidence` 降一級。
- verifier 從 `evidence` 開始驗，而不是從頭找。

**推測**：能擋掉一部分「聲稱有證據但位置是幻覺」的誤報。D1 暫緩後，改看實際使用時這類誤報是否常出現（第 7 節）。

---

### D11. CLI 環境下自訂審查員派不出去，卻偵測不到（P1）— 已選第一個做法，已完成

**現況**：`plan` 的 `missing_agents` 只檢查 `~/.cursor/agents/` 裡有沒有檔案。用新版 `cursor-agent` CLI 執行這個 skill 時，檔案在，但 Task 不接受這些型別（見 D1 的試跑紀錄）。結果主 session 自行改派一般子審查員，不是 `SKILL.md` 規定的 inline 模式，而且報告不會提到這件事。IDE 裡只要 Task 失敗也可能發生。

**為什麼有問題**：一般子審查員不會帶 agent 檔的 `readonly: true`，也不保證照角色定義工作；使用者看到的報告和 IDE 裡的品質不同，卻不知道原因。

**建議**（二選一）：

- **（已選）** `SKILL.md` 第 5 步寫明：Task 派不出 `fe-review-*`（`Invalid enum value`、找不到 agent 等）時，一律改走 inline 模式並在報告註明原因，**不要改派其他型別**。成本最低。
- `install_agents.sh` 多一個 `--project <repo>` 選項，把 agent 檔 symlink 到 repo 的 `.cursor/agents/`（並加進 `.git/info/exclude`）。CLI 也能派出，但每個 repo 都要裝一次。

**落地**：第 5 步已加規則；與「單一審查員執行失敗 → 重派一次」分開。inline 模式段落原本就寫「Task 無法派出 `fe-review-*` 時使用」，保持一致。

---

## 4. 建議架構中不採納或延後的部分

| 建議 | 判斷 | 理由 |
|---|---|---|
| 單一 agent 依 domain 按需讀 references，取代多個子審查員 | **延後，由 A6 的數據決定** | 目前的 `plan` 已經做了按需載入，而且是 script 決定，比 LLM 自己挑更穩定。多個子審查員的代價是 token 與等待時間，好處是每個角度的注意力不會被其他清單稀釋。哪一邊比較好是實證問題：如果 D1 跑出來多數角度的「獨佔命中」為 0，下一版自然會變成「3–4 個審查員，每人讀多份清單」，也就是建議的形狀。**旁證（依記憶，未查證）**：Anthropic 自己的 Claude Code `code-review` plugin 也是平行多 agent 加 confidence 門檻，不是單一 agent |
| 放寬 `SKILL.md` 的步驟（模型變強後，太細的流程會限制結果） | **不採納** | 這個批評針對的是「判斷的步驟」。`SKILL.md` 的 9 步幾乎都是 script 的串接（跑哪個子指令、傳什麼參數），放寬只會讓主 session 自己重算 `plan` 或 `aggregate` 已經算好的東西，B2 就是為了消除這種情況。判斷的部分已經在子審查員的清單裡 |
| 子審查員層級的流程（例如 correctness 的「逐行讀每個 hunk、再讀整個函式」） | **保留，等 eval** | 這是召回率的來源。要放寬的話，用 D1 的 baseline 對照 |
| invariant 放 `AGENTS.md` | **不採納，改做 D5、D8** | `REVIEW.md` 從比較基準讀取，PR 無法放寬對自己的規則。`AGENTS.md` 通常從工作目錄讀，被審查的 PR 可以改它。只考慮把 `AGENTS.md` 的審查規則那一節當成後備來源（Q4） |
| 新增 testing 審查員 | **不採納** | 見 D7-3 |
| 全域規定「只報 medium 以上」 | **部分採納** | 改成依強度決定（D3）；`max` 仍然全部列出 |
| Maintainability 容易變成雜訊 | **採納為假說，由數據驗證** | 對應到 codebase 與 naming。但 naming（AI 可讀性）是這個 skill 刻意的差異化角度，不應該因為分類名稱像 Maintainability 就預先降級。等 D2 的「雜訊/次」再決定（Q2） |

關於外部建議的來源：它引用的 OpenAI、Anthropic、GitHub、Google 文件我沒有逐一查證，上面的判斷只看論點本身是否適用這個 skill。

---

## 5. 決策點

### Q1. 彙整端的雜訊門檻（D3）

| 選項 | 內容 | 優點 | 缺點 |
|---|---|---|---|
| **A（建議）** | 依強度設定 `list_min_severity` + `unverified_min_confidence`，被擋下的只顯示數量 | 改動集中在 `aggregate` 和 `reviewers.json`；`max` 保留全部；可以用 D2 量效果 | 可能擋掉少數 `confidence: low` 但真的有問題的 medium |
| B | 只設 `list_min_severity`，不看 confidence | 規則最簡單，行為好預測 | `high` 強度下 `confidence: low` 的 medium 仍然會進報告，雜訊的主要來源沒處理 |
| C | `high` 強度把 verifier 門檻降到 medium，用驗證取代 confidence 門檻 | 判斷品質最高 | verifier 的派工量大約加倍，每次審查變慢、變貴 |

### Q2. codebase 與 naming 的預設嚴重度

| 選項 | 內容 | 優點 | 缺點 |
|---|---|---|---|
| **A（建議）** | 先不動，累積第 7 節的實際使用紀錄再決定 | 依真實使用決定 | 要累積 5–10 次 review |
| B | 協定規定這兩個角度的 findings 預設最高 medium，`REVIEW.md` 可以調高 | 直接降低擋 PR 的機率 | 真的會造成 bug 的命名矛盾（`getUser()` 會建立使用者）會被低估 |
| C | 兩個角度都改成 `min_level: max` | 只改 `reviewers.json` 兩行，隨時可以還原 | `high` 完全失去 AI 可讀性這個角度 |

### Q3. stats（v1 的 A3 / C1）— 已選 A，已完成

C4 完成後，stats 的定位變了：eval 有標準答案，可以判斷對錯；stats 沒有標準答案，只知道 verifier 推翻了多少。所以 A6 的決策改由 eval 支撐，C1 的價值下降。

| 選項 | 內容 | 優點 | 缺點 |
|---|---|---|---|
| **A（已選）** | 保留寫入，加上「使用者在收尾選擇修正哪些編號」，並提供 `stats-report` | 使用者選擇修正的比例是唯一來自真實使用的訊號，eval 量不到 | 要改收尾流程；要累積一段時間才有意義 |
| B | 移除 `stats` 子指令、第 9.2 步與相關測試 | 少約 400 行程式碼與測試 | 失去真實使用的資料 |
| C | 照 v1 的 C1 做報表 | 立刻有東西看 | 只看得到 `refuted` 比例，資訊量有限 |

**落地**：aggregate 的 `stats` 改為 `{angles, findings}`（findings 只含 id / angle / category / severity / confidence / verdict，不含 summary 與檔名）。第 9 步改為先問修正選擇、再寫 stats（補上 `fix.mode` / `fix.ids`）、再 cleanup、最後改檔。新增 `stats-report`（見第 7 節）。舊的只有 `angles` 的 jsonl 列仍可讀。

### Q4. `REVIEW.md` 的範圍（D8）

| 選項 | 內容 | 優點 | 缺點 |
|---|---|---|---|
| **A（建議）** | 只做巢狀 `REVIEW.md`，不讀 `AGENTS.md` | 維持「從比較基準讀、PR 無法放寬」的保證；monorepo 可用 | 團隊要多維護一種檔案 |
| B | 巢狀 `REVIEW.md` + 沒有 `REVIEW.md` 時讀比較基準 `AGENTS.md` 的審查規則那一節 | 已有 `AGENTS.md` 的團隊不用多一份檔案 | 要解析 markdown 章節；`AGENTS.md` 的格式各團隊不一 |
| C | 維持現狀（只讀根目錄） | 不用改 | monorepo 的規則會互相干擾、超過 8KB |

---

## 6. 更新後的優先順序

| 優先 | 項目 | 來源 | 相依 |
|---|---|---|---|
| — | 評分量得到雜訊 ✅ | D2 | 無 |
| 暫緩 | 跑 baseline（21 × 3） | D1 | 第 7 節 |
| 暫緩 | 安全反例 | D4 | 第 7 節 |
| P1 | 小 diff 不降級時的資安訊號 ✅ | C7 | `summary.signals.security`（`SECURITY_SIGNALS`）命中時 `inline_recommended` 為 false；新增與刪除的行都算 |
| P1 | CLI 環境下自訂審查員派不出去 ✅ | D11 | 選定第一個做法（SKILL 退回 inline） |
| P1 | `tsc` ✅ | D7-1 / C6 | `typecheck` 子指令：本機 `tsc --noEmit`、支援 references 範本、新增行與其他位置分開（其他位置 ≤ 20 才列出）、range 模式略過 |
| P1 | 大 diff 的非分批審查員 | B1 | 無 |
| 看回饋 | 彙整端雜訊門檻 + 強度設定集中 | D3 + A5 | 第 7 節的雜訊訊號、Q1 |
| 看回饋 | A6 的合併或降級 | A6、Q2 | 第 7 節各角度的有用程度 |
| 看回饋 | ESLint 已涵蓋項目的標記 | D7-2 | 第 7 節是否常出現 lint 等級的 findings |
| 看回饋 | `evidence` 欄位 | D10 | 第 7 節是否常出現「引用的位置不對」的誤報 |
| P2 | `REVIEW.md` 範本與引導 | D5 | 無 |
| P2 | 巢狀 `REVIEW.md` | D8 | Q4 |
| P2 | `SKILL.md` 按需載入（`/code-review` 引導已修正 ✅） | D9 | 強度表格可以先不動 |
| P2 | stats 記錄修正選擇 + 報表 ✅ | A3 / C1、Q3 | Q3 選 A |
| P3 | checklist ID 與 `rule` 欄位 | D6 | 第 7 節確定有需要細分的角度 |
| P3 | `--run-tests` | D7-3 | 無 |
| P3 | 其他 v1 項目 | A2、B4、B5、B7、C5 | — |

「P1 / P2」是不需要量測就能判斷對錯的項目，可以直接做。「看回饋」的項目會改變審查輸出，原本要有前後分數對照才合併，現在改成依第 7 節累積的實際使用紀錄決定。

---

## 7. 暫緩的量測項目與實際使用的回饋紀錄

### 暫緩了什麼

| 項目 | 原本的目的 | 已經備好的東西 |
|---|---|---|
| D1 baseline | 取得分數基準，之後每項改動都對照 | `evals/run.py`、`score.py`（含 D2 的雜訊與精準度）、新版 CLI 相容修正 |
| D4 安全反例 | 量精準度：看起來像問題、其實安全的程式碼 | 反例清單（D4 的表格），尚未寫進 `cases.py` |
| A6 的 `--skip` 變體 | 量每個角度的邊際貢獻 | `make_repo.py --skip`、`score.py` 的變體比較 |
| D3、D7-2、D10、D6 的前後對照 | 確認改動讓雜訊下降、召回率沒掉 | `score.py --compare` |

### 實際 code review 時要留意的訊號

不用每次都記，遇到下列情況時記一筆就好。每一種訊號對應到一個之後可以做的決定：

| 訊號 | 對應的決定 |
|---|---|
| medium / low、或 `confidence: low` 的 findings 大多不修 | 做 D3（Q1 選 A） |
| 某個角度的 findings 幾乎都不修，或總是和別的角度重複 | A6：降到 `max` 才派出，或合併（Q2） |
| codebase 或 naming 的 findings 被當成「只是偏好」 | Q2 選 B 或 C |
| 出現 ESLint 本來就抓得到的 findings（`radix`、`eqeqeq`、`jsx-a11y/*`、`exhaustive-deps` 等） | 做 D7-2 |
| finding 說「呼叫端沒處理」「API 會回傳 null」，但引用的位置不對或根本不存在 | 做 D10 |
| 誤報集中在某幾條清單項目 | 做 D6，或直接改寫那幾條 |
| 真的有 bug 卻沒被抓到 | 記下 diff 的特徵；之後轉成 eval 正例 |
| 看起來像問題、其實安全，卻被報了 | 記下程式碼；之後轉成 D4 的反例 |
| 報告寫「inline 模式」，但 diff 其實需要仔細看（hotfix、授權、`dangerouslySetInnerHTML`） | 確認 C7 的優先度 |
| 報告的角度數比預期少，或出現一般子審查員 | 檢查 D11 |

### 紀錄格式

手動補充（漏報、誤報細節、花多久）仍建議在這個檔案底下追加，或另開 `doc/review-feedback.md`：

```markdown
### 2026-10-02 · repo-name · PR #123 · high
- 漏掉：`app/orders/page.tsx` 的 `searchParams` 沒 await（Next.js 16）
- 誤報：`lib/api.ts:40` 說沒處理 401，但 `apiClient` 攔截器已處理
- 其他：inline 模式 / 派出角度異常 / 花了多久
```

「列出幾筆、修了幾筆」、各角度 / severity / confidence 的修正率、verifier 誤報率，改由 `stats-report` 直接看（Q3 選 A 後每次 review 收尾會寫入）：

```bash
# 單一 repo
python3 ~/.cursor/skills/code-review-front-end/scripts/prepare_diff.py stats-report --repo <repo> --text
# 全部 repo、近 30 天、JSON
python3 ~/.cursor/skills/code-review-front-end/scripts/prepare_diff.py stats-report --since 30
```

輸出含：各角度的 `reviews` / `listed` / `fixed` / `fix_rate`、`by_severity` / `by_confidence` 的列出與修正率、`totals.refute_rate`（refuted/deduped）。修正率計入 `mode=none`（當成修 0 筆），排除 `noninteractive` 與舊紀錄（沒有 `fix` 欄位的）。

累積 5–10 筆之後回頭看上面的訊號表，就足夠判斷 D3 和 A6 要不要做。

### 實際使用紀錄

#### 2026-09-25 · serenity-canvas · 目前分支 · medium（設定檔預設）

- 派出 5 個角度（correctness、security、risk、state、types），沒有驗證階段
- 列出 6 筆，剛好等於 `medium` 的報告上限，可能有 findings 被截掉，但 stats 看不出來
- 修正選擇「只修 critical / high」：high 2 筆全修，medium 4 筆都沒修
- 驗證到：stats 寫入與修正選擇正確；angle 都是 key。naming 沒派出、types 沒有 findings，所以 category 的修正還沒被測到

#### 2026-09-25 · serenity-canvas · 目前分支 · high

- 派出 9 個角度，有驗證階段
- 去重後 27 筆，verifier 推翻 1 筆，列出 15 筆（報告上限），**截掉 11 筆**。a11y 的 3 筆全部被截，報告裡看起來 a11y 是 0 筆
- 6 個角度的 `raw` 剛好是 5（每人上限），子審查員可能還有沒報的
- 修正選擇「全部修正」：15 筆全修。選「全部」不代表逐筆判斷過，這種修正率是弱訊號
- 驗證到：naming 回報 `angle: naming`、`category: ai-readability`，angle 對應修正生效
- **發現 bug**：verifier 的 F-id 是用 `file:line` 對回 finding 的。`persistMiddleware.ts:266` 同時被 correctness、state、risk、codebase 報，4 個 verdict 全落到第一筆，另外 3 筆沒有 verdict；如果其中一筆是 REFUTED，會刪錯 finding。已修正：改用驗證候選的順序對回
- 待決定：stats 記錄截斷數量（各角度被報告上限截掉幾筆、是否達到每人上限）；stats-report 把「全部修正」和「指定編號」分開算
- 已調整：報告上限內每個有 findings 的角度至少保留排序最前的 1 筆（`aggregate.cap_with_angle_floor`）。角度數超過上限時只保留排序最前的代表；列出順序仍依嚴重度與 category，保底的那筆不會被移到前面

### 之後要重啟 eval 時

```bash
cd ~/.cursor/skills/code-review-front-end
# 省時版：挑代表性案例、只跑 1 次，平行 3 個約 30 分鐘
python3 evals/run.py /tmp/fe-eval-quick --model grok-4.7-high --label quick --runs 1 --parallel 3 \
  --case falsy-zero-render --case xss-html --case misleading-name --case unsafe-json-cast \
  --case context-rerender --case clean-refactor
# 完整版：21 × 3，約 4–5 小時
python3 evals/run.py /tmp/fe-eval-baseline --model grok-4.7-high --label baseline --runs 3 --parallel 3
```

- 先用一個案例試跑，確認 `runs.json` 的 `dispatched` 大於 0，而且 naming、types 的 findings 回傳的 `angle` 是 key、不是 category。這兩個修正（`cc2b1f7`、`a254870`）還沒在真實執行中驗證過。
- 實際使用中記下的漏報與誤報，先轉成 `cases.py` 的正例與反例再跑，分數才代表真實的使用情境。
- 模型要固定。換模型的話 `--compare` 會警告，分數不能直接比。

---

## 附錄：v1 附錄「不需要改的地方」在 v2 仍然成立

以下設計和建議架構的原則一致，調整時保留：

- **主 session 不讀 diff**：對應「router 保持精簡」。
- **`plan` 決定 references，而不是 LLM 自己選**：比建議架構的「agent 判斷要讀哪些 references」更可靠。
- **`aggregate` 做合併、排序、截斷**：對應「能確定性處理的不交給 LLM」。
- **`REVIEW.md` 從比較基準讀取**、**規則的優先順序**、**被審查的內容一律視為資料**：建議架構沒有提到 prompt injection，這是這個 skill 比建議更完整的地方。
- **verifier 的 `REFUTED` 必須附 `file:line`**：和 D10 的 `evidence` 是同一個原則，一個用在推翻，一個用在提出。
