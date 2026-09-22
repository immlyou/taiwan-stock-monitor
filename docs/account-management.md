# Google 帳號管理（v5.3.0）

## 使用方式

管理員由側欄「系統 → 帳號管理」或 `/admin/accounts` 開啟。新增 Google Email
只是加入允許名單，不會寄信；請自行分享網站網址。對方須使用相同且經 Google 驗證的
Email 登入。Google OAuth 專案若仍處於 Testing，還要將對方加入 Google 的 test users；
應用程式邀請不會修改 Google Cloud 設定。

| 角色 | 行情／自己的資料 | 編輯與分析提交 | 管理帳號／全域 refresh |
| --- | --- | --- | --- |
| 管理員 | 可以 | 可以 | 可以 |
| 一般使用者 | 可以 | 可以 | 不可以 |
| 唯讀 | 可以 | 不可以 | 不可以 |

唯讀仍允許 `POST /quote/realtime/batch`（批次讀取行情），但拒絕其他寫入 HTTP methods，
以及舊有會執行警報評估的 `GET /alerts/check`。GET 分析與系統內部行情快取仍可執行。
所有角色均不跨使用者讀取投組、自選股、警報、設定、日誌或預測；管理員只能管理帳號屬性。
目前不提供逐頁自訂權限、移交 Google 身分、帳號刪除或自動寄送邀請。

## 初始帳號與遷移

- 延用 Vercel 的 `AUTH_ALLOWED_EMAIL` 作為**一次性初始管理員** Email，不再是每次登入的單帳號 allowlist。
- 初始帳號必須有有效的既有 Google JWT 或完成 Google OAuth。空白／無效設定不開放註冊。
- `accounts.json` 尚不存在時，只有這個 Email 可初始化為管理員；其他 Email 拒絕。
- 已存在的 Google JWT 可初始化既有管理員，但 `last_login_at` 留空，直到下一次 OAuth 成功。
- 其他人必須先受邀，再完成 OAuth；舊 JWT 不能綁定尚未啟用登入的邀請。
- 一旦初始化，Email 環境變數不能覆蓋已保存角色或繞過停用。現有 user-id 資料目錄不搬動。
- 不支援多程序／多副本寫入；沿用單 worker + Volume + 每檔鎖 + atomic rename。

## 安全邊界與稽核

`STOCK_API_KEY` 是具有服務層權限的秘密；不能交給使用者。裸 service-key 請求保留
既有 CLI／SSR 相容性。管理 API 另外要求已註冊的管理員 actor；瀏覽器流量只能經 Next.js
gateway，它從已簽章 Google session 重建 `X-User-ID`、`X-User-Email` 與 bootstrap header。
`/internal/accounts/google-login` 僅給 NextAuth callback；generic proxy 拒絕 internal 路徑與
可造成路徑正規化的片段。後端不信任 JWT 中的 role，而逐次讀取 registry。

不能調整自己的角色／狀態。變更時重新檢查操作者與 revision，並保留至少一位啟用且已綁定
Google 的管理員。損毀／空 registry fail closed，不能當成新系統自動重建。
API 拒绝停用帳號的下一次請求；已在執行的請求或排程不會被強制取消，已下載的資料也不能收回。
客戶端每 30 秒／focus 更新帳號狀態；後端權限變更不需等待這個輪詢。
停用或唯讀帳號會略過後續個人通知與預測驗證排程。尚未初始化 registry 時保留舊排程行為。

成功 OAuth 登入、邀請和角色／狀態變更記錄於同一 atomic registry；保留最近 500 筆，UI 顯示
最近 100 筆。不記錄 token、密碼、IP 或完整 Google profile。這不是完整的安全事件日誌，
不包含登入失敗或新功能啟用前的歷史。管理員清單与權限不持久化到 localStorage。

## 部署順序與檢查

1. 備份 Railway Volume 的資料，確認單 worker 與持久 Volume。
2. Vercel `AUTH_ALLOWED_EMAIL` 保持原管理員 Email，兩端 `STOCK_API_KEY` 必須一致；不需新增 provider。
3. **前後端需協調切換**：舊前端不送 Email，升級後端後會拒絕舊前端帶 user-id 的請求；新前端也不能安全搭配沒有帳號驗權的舊後端。安排短暫維護窗口，先部署後端成功，再立即部署前端。
4. 用原管理員登入，確認帳號後台與私人資料仍正確。進行真正 Google OAuth 登入確認最近登入紀錄。
5. 加入測試帳號，驗證一般使用者／唯讀／停用與跨帳號隔離；不要用正式投組資料做破壞測試。
6. 回滾不可只退回不含帳號驗權的後端（新前端會讓已簽章使用者通行）。兩端協調回滾至單帳號版本；保留 registry 檔案供恢復。

驗證命令：Python `pytest tests/test_accounts.py`；frontend `npm run test:unit`、
`npm run lint`、`npm run build`、`npm run test:e2e:blocking`、`npm run test:e2e:contract`。
契約測試使用臨時帳號資料與測試簽章，不代表已完成真實 Google 授權視窗測試。
