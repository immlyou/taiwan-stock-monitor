# AI 選股與指標方法稽核 — 2026-09-22

## 結論

工程正確性與投資有效性是兩件事。本輪修正可重現的時序、公式、缺值、統計與呈現錯誤；**不能將目前 XGBoost／LSTM／規則選股宣稱為已驗證能獲利的模型**。不依這次回測結果調參，也不以舊版 seed 或測試覆蓋率代替模型績效。

本文件記錄 5.4.0 發布前的本機稽核；實際 commit／部署狀態以發布驗證為準。稽核未呼叫付費 LLM、交易 API，未改動正式環境或正式追蹤資料。研究資料取自既有可信備份，離線 walk-forward 不連網下載行情。

## 檢查與修正範圍

| 模組 | 確認問題／修正 | 有效性判定 |
| --- | --- | --- |
| RSI / ATR / ADX / MFI | 修正 Wilder 初值與遞推、單邊行情／零流量、缺價重新暖機；週線改為週五結束的交易週 | 手算與 TA-Lib 獨立參考值通過不等於訊號可獲利 |
| XGBoost | 共用市場交易日，不壓縮缺價；排除最新無價股票；零因子有效，缺值保留；60 日暖機；共用 RSI | 14 因子回歸器，預測 20 交易日原始價格報酬；尚無可投資證據 |
| LSTM / EWMA | 明示實際模型與資料日；缺價後要求連續歷史；固定 seed、隔離 RNG、CPU 單執行緒；共用 RSI | 150 個近期樣本、18 epochs 的即時小模型；非預訓練成熟模型，尚無樣本外優勢證據 |
| 量化六構面 | 反向百分位端點、缺失警示資料假滿分、同日修訂快取、子集評分母體、缺失法人流量、跨股票缺價干擾 | 透明但人工設定的權重，並非學得／驗證過的預期報酬 |
| 操盤雷達 | 真實零分不再回填 50；「機率」改為規則分；歷史代理去掉今日活躍清單、延後進場並加成本、缺失籃子不報部分勝率 | 歷史代理公式不同於現行雷達，只取歷史代號排序前 350 檔；視窗重疊，不代表實盤或獨立樣本 |
| 通用回測 | 回呼只接收前一交易日以前資料；當日收盤成交；缺報價沿用估值但不成交；部分賣出入帳、買方成本分攤、初始資本基準、未平倉不算失敗交易 | 仍是原始價格、簡化漲跌停；未建模公司行動、完整流動性與滑價 |
| Sharpe / Sortino / 下行風險 | Sharpe 改為日超額報酬均值／標準差；Sortino 以全部觀測的低於門檻平方平均計算，連續虧損不再變成正無限大 | 年化 252 日，風險利率為設定假設，並非即時利率 |
| 前向追蹤 | XGBoost 以實際交易日驗證，固定 T+N 報價；同資料日去重；來源與模型版本分開；平均報酬排除 pending | 不重新解讀舊紀錄；新版需累積新的完成樣本，不能沿用舊模型勝率 |
| 投資顧問 | 移除分數直接換算年化報酬與「可行」判定，回傳未校準／尚無法評估；LLM prompt 不得補造數字 | 配置與文字為規則／敘述，不是報酬預測模型 |
| 參數優化 | 拒絕未實作 RSI／突破／停損參數；限制搜尋範圍；分開訊號、成交與持有日；列明成本情境；未計算勝率為 null | 樣本內挑最佳，不是 walk-forward 或樣本外驗證 |

其他既有指標的計算慣例保留並應與外部軟體區分：SMA 可用不足完整視窗；EMA／MACD 採首筆價格初始化、`adjust=False`；Bollinger 採樣本標準差 `ddof=1`；KD 是 EMA-span 變體，不是 50 起始、alpha=1/3 的台股常見版本，也不是 TA-Lib STOCH 的 SMA 版本；PSAR 是上漲初始化的簡化變體，補上空資料／缺價後重啟保護。不可宣稱所有指標與所有看盤平台逐點相同。

Claude 個股／新聞摘要與異常掃描做了程式及呈現語意檢查；沒有執行付費 LLM 評測、建立標註新聞集或測量幻覺率。異常掃描／Hidden Gems 的人工門檻與加權分數，也沒有被當作已校準機率。獨立 Markowitz 優化器不在這次完整實證範圍，不能因共用風險公式修正而宣稱其配置已通過樣本外驗證。

## 重跑研究：XGBoost 24 期

後續經使用者確認，新增獨立的交易生命週期核對：24/24 期已核對、23/24 期已結清、1 期停牌未平倉。下表的原始指定日口徑不變；新口徑及證據見 [生命週期核對](xgboost-lifecycle-review.md)。

- 快照截止：2026-09-21；來源備份 SHA-256：`a82105aff9a4cdaa04067080e9443d86a37905350cba15de8fb42be14e5d2d30`。
- 訊號日：2024-09-27 至 2026-08-24，24 期，每 20 個市場交易日重訓；Top 20；未做結果導向調參。
- 模型：`xgb-2-calendar-wilder-missing`；方法：`wf-2-next-session-costs-fixed-selection`。
- 資料含股票與 ETF 等既有報價代號，沒有事後挑選只有完整未來資料的股票母體。
- IC 使用 T 收盤 → T+20 收盤的毛報酬，對應模型目標；交易情境為 T+1 收盤買入 → T+20 收盤賣出，實際持有 19 個交易日。
- 情境成本：買方 0.1425%、賣方 0.4425%，各加 10 bps 滑價。這是明示假設，不是個別券商／商品實際費率；最低手續費、成交量限制、停牌清算與公司行動未完整模擬。

| 項目 | 本輪結果 | 解讀 |
| --- | --- | --- |
| 平均 IC | 0.0004 | 接近零，無穩定排序優勢證據 |
| IC IR | 0.0033 | 不支持穩定方向性 |
| 正 IC 期數占比 | 45.83% | 未見大多數期數正向 |
| Top 20 報價完整期數 | 9 / 24 | 其餘 15 期不可拿倖存股票替補後當作完整籃子 |
| 完整 9 期平均命中率 | 43.33% | 有條件子集描述，**不是 24 期模型勝率** |
| 完整 9 期平均扣成本報酬 | -1.93% / 期 | 不是年化／連續投組淨值，亦不是全期績效 |
| 全候選籃子完整期數 | 0 / 24 | 基準與超額報酬維持 unavailable，不能宣稱打敗大盤 |

原始逐期紀錄列出選股名單、缺少到期報價的代號、資料涵蓋率、成本與資料／程式雜湊，位於 `reports/model-audit-walk-forward-24-final.json`（本機產物，不覆蓋正式 `data/xgboost_backtest.json`）。第一次隔離 XGBoost-only 環境與其後含 PyTorch 的修正環境重跑，24 期數值相同。

這是 **現有快照的研究結果**，不是完全 point-in-time 回測：月營收快照索引已是次月日期，卻仍缺少每次公告版本／更正時間證據；原始收盤未調整拆股、除息；下市／停牌資料不完整。沒有任意補零或將缺失當獲利／虧損。未來要判定可用性，需先補這些資料、制定固定母體與成交模型，再在未用於調參的期間做分段樣本外比較、成本敏感度與區間估計。

## 可重現方式

使用 Python 3.11，安裝 `requirements-api.txt` 與 `streamlit`；本次主要數值套件：numpy 2.4.6、pandas 3.0.6、scikit-learn 1.9.1、XGBoost 3.2.0。可信備份內的 pickle 可執行程式碼，**不可套用到不可信檔案**。

```sh
python scripts/backtest_xgboost.py \
  --snapshot-tar /absolute/path/to/trusted-data-backup.tar.gz \
  --as-of 2026-09-21 --periods 24 --step 20 --top-n 20 --forward 20 \
  --out reports/model-audit-walk-forward-24-final.json
```

腳本只讀快照，不解壓覆寫資料、不連網載入市場資料；報告包含資料來源、各資料集 hash、執行參數與方法檔案 hash。更改任何公式或資料後，應重新產生結果，不可將本報告重新命名成新版驗證。

## 原生套件相容性追查

依 `diagnosing-bugs` 的最小重現流程，macOS arm64 上 PyTorch 2.14.0 與 XGBoost 3.2.0 共存時，Torch-first + float64 XGBoost label conversion 能觸發 native segmentation fault；只調換載入順序雖可修復 XGBoost，卻仍可使多執行緒 LSTM 崩潰。最終採 XGBoost 先載入、PyTorch CPU intra-op 單執行緒，並以同一子程序實際訓練兩個模型做回歸測試；不是只測 mock API 或任一模型單獨可用。未驗證所有 OS／套件組合，未設定忽略 OpenMP 衝突的全域環境變數。

## 驗證紀錄

- 後端：1,204 項通過，0 跳過；沿用 CI 的 60 秒 timeout 與 85% coverage gate，既有 coverage 設定下 `core` 覆蓋率 87.75%。其中 27 項為本輪方法學回歸測試；另含實際 PyTorch／XGBoost 同程序訓練測試。
- 前端：52 項 unit 通過；ESLint、TypeScript／Next.js production build 通過。
- 登入與核心 blocking E2E：15 項通過、0 retries，包含回測無定義比率／缺少 benchmark 時的頁面保護。
- 真實前後端契約 E2E：5 項通過、0 retries；模型新增案例走 Next.js proxy → FastAPI → 真正 XGBoost／EWMA，以固定市場 fixture 驅動，不假造模型 response。
- Ruff、`git diff --check` 通過。Excel 年化欄位修正後，原本以 skip 放過的三個 Excel 案例改成真正斷言。
- API endpoint 測試隔離 production lifespan，避免啟動背景真實資料預熱；啟動預熱另由既有 `test_xgboost_resilience.py` 專門驗證，未停用正式預熱或降低測試門檻。

獨立參考 golden fixture 不依賴 CI 安裝 TA-Lib。以上為本機驗證，不代表 GitHub CI 或正式部署已完成；登入使用本機測試 JWT，不宣稱重新跑過正式 Google OAuth consent。

## 公式／方法參考

- [TA-Lib RSI 文件及來源索引](https://ta-lib.github.io/ta-doc/indicator/RSI.htm)；RSI／ATR／ADX／MFI 另以本機 TA-Lib 0.8.1 產生獨立對照值。
- [Quantopian empyrical 原始實作](https://github.com/quantopian/empyrical/blob/master/empyrical/stats.py)：日報酬 Sharpe 與 downside deviation / Sortino 的方法比較。
- [scikit-learn 機率校準文件](https://scikit-learn.org/stable/modules/calibration.html)：分數不等於經獨立驗證的事件機率；本輪沒有假裝完成校準。
- [FinLab 官方 FAQ：資料索引與公告時序](https://finlab.finance/docs/en/faq/)：報告期間不能直接當作資料公開日；時間截斷不等於歷史修訂資料已受控。
