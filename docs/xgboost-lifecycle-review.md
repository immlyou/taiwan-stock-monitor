# XGBoost 24 期交易生命週期核對

## 完成標準與結果

使用者確認改採完整交易生命週期：未成交留現金、無到期價延後出場、拆股調整股數、下市只接受有證據的現金結算。**不改原始名單、不把缺價填零、不將未平倉寫成已結清。**

資料截止 2026-09-21，核對 2024-09-27 至 2026-08-24 的同一批 24 期、每期 Top 20、共 480 筆。

| 指標 | 結果 | 定義 |
| --- | --- | --- |
| 已核對期數 | **24 / 24** | 每筆均有可解釋的交易狀態，含已識別停牌的未平倉 |
| 已結清期數 | **23 / 24** | 該期每筆已賣出／結算或根本未買入而保留現金 |
| 未平倉期數 | **1 / 24** | 2026-03-30 期持有 1589，截止日仍無後續成交價 |
| 未解釋資料缺口 | **0 期** | 不等於已取得所有股息／公司行動資料 |
| 原始指定日報價完整期數 | **9 / 24（保留）** | 原本的嚴格指定日成交價口徑，不改寫成 24 |
| 原始平均 IC | **0.0004（保留）** | 本次是交易核對，不是重訓、重新調參或重新估算 IC |

480 筆：準時出場 451、未成交留現金 16、延後出場 12、停牌未平倉 1。後三類共 29 筆，影響原本 15 個不完整期數。

## 確認的原因與事件

- 6902 在 2024-11-01 的官方紀錄為成交量 0、收盤價 `--`；不能以補抓不存在的成交價修正。[TWSE 原始月行情](https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=20241101&stockNo=6902)
- 3202 自 2025-04-07 停止買賣，位於原定進場日，模擬委託未成交、保留現金。[櫃買公告](https://dsp.tpex.org.tw/web/announcement/announcement_detail.php?content_file=MTE0MDAwMzQ4MzEuaHRtbA%3D%3D&content_number=MTE0MDAwMzQ4MzE%3D)
- 1225 自 2025-04-07 停止買賣，2025-06-23 才恢復；原定進場日無成交，不延後挑選更有利進場日。[停止公告](https://wwwc.twse.com.tw/staticFiles/news/news/tsecnews/8a8216d695c717e00195f0f1af4700a4.pdf)、[恢復公告](https://investoredu.twse.com.tw/Mobile_Pages/..%2FFileSystem%2FFileUpload%2Ff8532e20-3724-4f3e-8dbf-7649f55f3d54.pdf)
- 00631L 在 2026-03-25 至 03-30 停止交易，03-31 以 22：1 分割後恢復。本研究將一股調整成 22 股後，使用 03-31 收盤價 19.26 模擬延後出場；不是把價格由 500.45 變 19.26 當作虧損約 96%。[官方分割公告](https://wwwc.twse.com.tw/zh/ETFortune/announcement?company=A00005&date=20260330&fund=00631L&seq=1&type=other)
- 1589 在 2026-03-31 模擬買入 6.6 元，4 月 7 日起停止買賣，快照最後報價為 4 月 2 日的 5.54 元，截至 9 月 21 日無後續價。保持 `open_suspended`、實現報酬 `null`；最後價格僅舊估值，不能視為可成交價或確定可回收金額。[TWSE 停止買賣公告](https://investoredu.twse.com.tw/Mobile_Pages/..%2FFileSystem%2FFileUpload%2Fd1edd836-fd52-4bf4-9936-badafcb0586d.pdf)

依 diagnosing-bugs 流程建立可失敗的原始 9/24 檢查，對照行情量價與官方事件；原因為真實無成交／停牌／拆分，不是統一資料漏抓。需求確認後以 `accounted_periods` 建立新的完成 gate；`settled_periods` 和原始報價率保持獨立，避免改名掩蓋風險。

## 功能與規則

- `core/xgboost_lifecycle.py`：對凍結名單進行逐筆狀態處理。支援 split、halt、cash_dividend、cash_settlement；事件必須有唯一 ID 與證據 URL。未知資料缺口仍為 `unresolved_data`，不會自動當作現金或虧損。
- 進場日無普通交易收盤價且成交量少於一張，或已核對停牌，於本日收盤情境判定未成交；現金占比保持原本每檔 5%，不把資金重新加碼其他股票。**這是明示成交模型，不代表當日任何市場／零股皆不能成交。**
- 延後出場逐日尋找第一筆有效收盤價，不挑最佳價；若仍無價，只接受有證據的現金結算，或已核對停牌之未平倉。未成交現金不算股票勝率。
- 每期淨報酬只在全部結清時提供；持有停牌股的期數保留 `null`。可另讀取 `marked_return`，但它含陳舊估值，未假扣出場費，不是已實現報酬。
- 不將不同出場日期的期報酬串成投組 CAGR，也不宣稱資金可同時重複投入重疊持倉。
- 新 API：`GET /strategy/ai-xgboost/lifecycle`，沿用驗證邊界，只讀版本化研究產物，HTTP 請求不重訓模型。
- AI 選股頁獨立顯示核對／結清／原始報價率，逐期明細、未平倉提示、事件來源、下載 JSON；載入失敗可重試。即時模型失敗不阻止研究報告載入。
- 原 walk-forward／live-accuracy API 的語意不變，既有 production／個人預測紀錄未改動。

## 可重現資料與執行

版控 `research/` 下保存原始研究、事件清單、核對產物；只含市場研究資料，不含憑證、個人投組或原始大型行情快取。

```sh
python scripts/reconcile_xgboost.py \
  --study research/xgboost-frozen-study-2026-09-21.json \
  --snapshot-tar /absolute/path/to/trusted-data-backup.tar.gz \
  --as-of 2026-09-21 \
  --events research/xgboost-corporate-actions.json \
  --require-accounted 24 \
  --out research/xgboost-lifecycle-2026-09-21.json
```

腳本會驗證 close／volume 快照雜湊與原研究一致，記錄事件檔及程式雜湊；未達指定核對期數就非零退出。`24 / 24 accounted` 不會通過成 `24 / 24 settled`。pickle 只能使用可信備份。離線重建不下載市場資料、不執行交易。

## 仍然不能宣稱的事項

這是固定快照的 24 期研究核對，並非全市場公司行動資料庫、每日自動更新服務、實際成交紀錄或模型有效性證明。事件清單尚非完整股息、減資與公司行動 feed，因此績效不是完整含息總報酬；最低手續費、整股張數、漲跌停成交與市場容量仍未完整建模。1589 必須等待實際恢復交易或可驗證結算事件，才可將其期數列為已結清，不能靠程式保證。

以下為 5.4.0 發布前本機驗證；實際 commit／部署狀態以發布驗證為準。本機全套後端 1,216 項通過（新增生命週期 12 項），發布前重跑 coverage 87.73% 維持 85% gate；前端 unit 52 項、真實 proxy/API E2E 5 項、登入／核心 blocking E2E 15 項通過，ESLint／TypeScript／Next.js build 通過。研究產物與原研究、事件檔、執行程式的 SHA-256 一致，24/24 核對 gate 通過。新增停牌期間拆股與配息的估值守恆測試，避免把舊價格所含股息再加一次。
