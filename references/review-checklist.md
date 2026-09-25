# 前端 Review Checklist

只檢查使用者指定的 focus；沒有指定時檢查全部。先讀 diff，再按需讀 review root 的完整函式、呼叫端與專案規則。

## Correctness

- 條件、falsy 值、邊界、日期時區與型別轉換是否在實際輸入下出錯。
- 非同步是否漏 await、吞錯、產生競態、重複送出或沒有清理 listener／subscription。
- props、API、route、storage key 或 export 改動是否同步更新使用端。
- server/client 邊界、狀態同步、cache invalidation、loading/error/empty 狀態是否完整。
- 外部資料、JSON、URL 與表單輸入是否在執行期驗證，而不是只靠 TypeScript assertion。

## Risk

- 使用者輸入是否進入 HTML、URL、redirect、log、analytics 或 client bundle。
- 權限是否只在前端檢查；Server Action、Route Handler 與 API 是否重新驗證身分和輸入。
- 機密、個資與內部網址是否可能暴露；token 是否放進 localStorage。
- 變更是否需要後端、環境變數、資料遷移或部署順序配合。
- 互動元件是否有鍵盤操作、可讀名稱、label、focus 與錯誤提示。
- 是否會造成明顯 re-render、記憶體洩漏、巨大 bundle 或大量資料下的阻塞。

## Maintainability

- 是否重複實作專案已有的元件、hook、util、API client、常數或型別；提出時附既有位置。
- 新寫法是否違反 repo 明確規則或附近穩定慣例，並造成可描述的行為差異。
- 名稱、註解、型別與實際行為是否矛盾；不要只回報主觀命名偏好。
- 元件責任、state 所在層級與 client boundary 是否讓修改範圍無故擴大。

## 回報門檻

- 只回報這次 diff 引入或確實暴露的問題。
- 必須能指出變更行、失敗情境與影響；沒有證據就不要列。
- 格式、排序、偏好與純重構建議不算 finding，除非違反 repo 明確規則並造成具體風險。
