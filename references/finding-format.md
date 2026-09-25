# Finding 格式

reviewer 最後只輸出一個 JSON 物件，不加 markdown fence：

```json
{
  "lens": "correctness",
  "status": "ok",
  "findings": [
    {
      "severity": "high",
      "confidence": "high",
      "file": "src/OrderForm.tsx",
      "line": 42,
      "summary": "重複送出會建立兩筆訂單",
      "impact": "使用者快速點擊兩次送出按鈕時會送出兩個請求。",
      "suggestion": "送出期間停用按鈕，並在 handler 開頭拒絕重入。"
    }
  ],
  "notes": "無法完成的部分；沒有就省略"
}
```

- `lens` 必須是派工指定的 `correctness`、`risk` 或 `maintainability`。
- `status` 為 `ok` 或 `partial`。
- `severity` 為 `critical`、`high`、`medium`、`low`。
- `confidence` 為 `high`、`medium`、`low`。
- `file` 使用 repo-relative path；`line` 必須是 diff 中的變更行。
- `summary` 描述問題，不寫修法；`impact` 寫會在什麼情境造成什麼結果。
- 沒有問題時傳空陣列。不要回報 lint 或 typecheck 已列出的同一問題。
