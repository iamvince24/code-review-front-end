# Framework Notes

只讀與 context 偵測到的 framework 對應段落。

## React / Next.js

- render 中呼叫 handler、用非 boolean 值做 `&&` render、effect dependency 或 cleanup 錯誤。
- Server Component 傳不可序列化值給 Client Component；`use client` 邊界放得過高。
- Server Action 與 Route Handler 缺少伺服器端授權或輸入驗證。
- App Router cache、`revalidatePath`／`revalidateTag`、dynamic route params 與 search params 使用錯誤。
- `dangerouslySetInnerHTML` 的來源未消毒；把 secret 放進 `NEXT_PUBLIC_*`。

## Angular

- Observable 手動 subscribe 後沒有 cleanup，或可以改由 async pipe／`takeUntilDestroyed` 管理。
- `OnPush` 元件直接 mutation input，導致畫面不更新。
- `bypassSecurityTrust*`、動態 template 或不安全 URL 繞過 sanitizer。
- reactive form 的 disabled、validator、valueChanges 與錯誤狀態不同步。

## AngularJS

- `$scope` listener、watcher、timer 或 subscription 沒在 destroy 時解除。
- digest 外的 callback 更新資料卻沒有觸發 digest，或在 digest 內多餘 `$apply`。
- `$sce.trustAsHtml`、`ng-bind-html` 或動態 expression 接收外部內容。
- directive scope binding、controllerAs 與雙向 binding 改動破壞既有呼叫端。
