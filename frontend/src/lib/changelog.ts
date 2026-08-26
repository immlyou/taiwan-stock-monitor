export type ReleaseTag = 'Major' | 'Feature' | 'Fix' | null

export interface ReleaseNote {
  version: `v${number}.${number}.${number}`
  date: string
  tag: ReleaseTag
  changes: readonly string[]
}

/**
 * v4.0.0 之後的版本記錄。
 *
 * 舊版記錄仍保留在 settings page；近期版本獨立成可測試資料，避免頁首版本
 * 與時間軸再次各自停在不同版號。
 */
export const RECENT_CHANGELOG = [
  {
    version: 'v5.1.1',
    date: '2026-08-26',
    tag: 'Fix',
    changes: [
      '可靠性修正：XGBoost 前端總運算時限調整為 45 秒，取消隱性自動重試，逾時後改由使用者決定是否重試',
      '可靠性修正：Next.js 代理層為 /strategy/ai-* 提供 65 秒上游運算預算',
      '效能優化：服務啟動時背景預熱 XGBoost top-20，之後每 45 分鐘更新，早於一小時 TTL 到期',
      '效能優化：XGBoost cache key 加入 single-flight，同一服務進程的並行 cold miss 只訓練一次',
      '體驗改善：錯誤區分為運算逾時、暫時不可用與依賴缺失，不再一律誤報 scikit-learn 未安裝',
      '體驗改善：重新運算失敗時保留帳號快取的上次成功結果，顯示重試狀態並提供手動重試',
      '測試補強：新增 45/65 秒 timeout、錯誤分類、single-flight、啟動預熱、排程與登入後 stale-result E2E 契約',
    ],
  },
  {
    version: 'v5.1.0',
    date: '2026-08-24',
    tag: 'Feature',
    changes: [
      '功能新增：即時行情採 Fugle / TWSE 即時優先，FinLab 收盤資料自動 fallback',
      '功能新增：即時報價頁標示資料來源、盤中狀態、即時性與報價時間',
      '功能升級：Portfolio、Watchlist 與個股頁全面接入即時優先報價',
      '可靠性修正：批次報價允許單一 provider 失敗並自動降級，不因部分股票失敗中斷整批結果',
      '資料契約：統一即時報價欄位與前後端 freshness 判定，補齊 provider、API 與登入後 E2E 測試',
    ],
  },
  {
    version: 'v5.0.1',
    date: '2026-08-24',
    tag: 'Fix',
    changes: [
      '可靠性修正：代理層與前端 API 避免阻塞事件迴圈、重複 timeout 與 retry storm',
      '流程修正：新帳號第一次開啟 Portfolio / Watchlist 時可直接建立 default 資料，不再因 404 卡住',
      '資料隔離：SWR localStorage cache 改為依 Google user id 分帳號保存，舊版未隔離 cache 自動淘汰',
      '錯誤處理：Portfolio、Watchlist、Alerts、Journal、Settings 與個股頁補齊載入失敗、保留舊資料與重新載入狀態',
      '契約補強：settings / notification 前後端欄位與秘密遮罩流程加入單元及 API 契約測試',
      'CI 強化：登入後核心功能 Playwright E2E 納入 blocking pipeline，包含新帳號首次建立流程',
    ],
  },
  {
    version: 'v5.0.0',
    date: '2026-08-23',
    tag: 'Major',
    changes: [
      '重大變更：登入系統改用 Google OAuth，移除共用密碼登入流程',
      '安全強化：Google 帳號 owner allowlist，同時保護頁面、Next.js API proxy 與 FastAPI 使用者身分',
      '資料隔離：Portfolio、Watchlist、Alerts、Journal、Settings、Predictions、Saved Strategies 與通知狀態全面依帳號分區儲存',
      '秘密保護：Telegram token、SMTP 密碼等設定只回傳 configured 狀態與遮罩，不把既有秘密送回瀏覽器',
      '功能升級：Alerts 2.0 支援規則評估、PATCH 更新、通知節流與多帳號排程',
      '功能新增：Portfolio what-if／診斷工具支援持股配置、集中度、風險與調整情境',
      '架構調整：Next.js proxy 僅轉送伺服器驗證的 user id，忽略瀏覽器自行提供的身分 header',
    ],
  },
  {
    version: 'v4.1.0',
    date: '2026-07-16',
    tag: 'Fix',
    changes: [
      '可靠性修正：SafeJSONResponse 遞迴清理 NaN / Infinity，市場摘要缺資料時安全降級',
      '可靠性修正：/ready 改為非阻塞檢查，避免健康探針拖慢 API event loop',
      '效能優化：DataLoader 以 per-key download lock 防止同一資料集被並行重複下載',
      '效能優化：市場資料 loader.get 移至 executor，重運算不再阻塞其他 API 請求',
      '資料正確性：加權指數改取 TWSE 官方價格指數收盤值，補強 FinLab 熔斷器與 API contract 測試',
    ],
  },
  {
    version: 'v4.0.1',
    date: '2026-06-26',
    tag: 'Fix',
    changes: [
      '資料正確性：全站統一使用加權股價指數，不再誤顯示發行量加權報酬指數',
      '資料正確性：盤後總覽、大盤 ticker 與市場摘要共用一致 TAIEX 來源與漲跌計算',
      '顯示修正：三大法人欄位與單位清理，避免不同頁面數字定義不一致',
    ],
  },
] as const satisfies readonly ReleaseNote[]

export const CURRENT_VERSION = RECENT_CHANGELOG[0].version
