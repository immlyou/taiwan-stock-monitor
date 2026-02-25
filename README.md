# 台股戰情中心

基於 FinLab API 的台股分析與選股系統，使用 Streamlit 建構。

## 功能特色

- 25 個功能頁面，涵蓋選股、回測、籌碼分析、財報分析、AI 選股、社群輿情等
- 整合 FinLab API 提供完整台股數據
- 支援多種選股策略（價值投資、成長投資、動能投資）
- 即時報價與盤後總覽
- 每日晨報自動生成

## 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 設定 FinLab API Token

複製範本檔案並填入 Token：

```bash
cp .env.example .env
# 編輯 .env 填入你的 FINLAB_API_TOKEN
```

### 3. 更新資料（首次使用或每日更新）

```bash
python scripts/daily_update.py
```

### 4. 啟動應用程式

```bash
streamlit run app/main.py
```

預設開啟 http://localhost:8501

## 目錄結構

```
taiwan-stock-monitor/
├── app/                    # Streamlit 應用程式
│   ├── main.py            # 主頁面
│   ├── pages/             # 25 個功能頁面
│   └── components/        # UI 元件
├── core/                   # 核心邏輯
│   ├── data_loader.py     # 資料載入
│   ├── cache_warmer.py    # 快取預熱
│   ├── strategies/        # 選股策略
│   └── ...
├── scripts/               # 自動化腳本
│   └── daily_update.py    # 每日更新
├── config.py              # 系統設定
├── .env                   # API 金鑰（從 .env.example 複製）
├── .streamlit/            # Streamlit 設定
└── *.pickle               # 資料快取檔
```

## 功能頁面

| 頁面 | 說明 |
|------|------|
| 儀表板 | 市場概覽與重要指標 |
| 選股篩選 | 多維度條件選股 |
| 回測分析 | 策略歷史回測 |
| 個股分析 | 單一股票深度分析 |
| 策略管理 | 自訂策略儲存 |
| 參數優化 | 策略參數調優 |
| 風險分析 | 投資組合風險評估 |
| 產業分析 | 產業輪動分析 |
| 投資組合 | 持股管理 |
| 系統設定 | 通知與系統設定 |
| 自選股 | 個人關注清單 |
| 警報設定 | 價格與指標警報 |
| 比較分析 | 多股比較 |
| 籌碼分析 | 三大法人動向 |
| 財報分析 | 財務報表分析 |
| 交易日誌 | 交易紀錄 |
| 每日晨報 | 每日市場摘要 |
| 即時報價 | 盤中即時行情 |
| 市場熱力圖 | 視覺化市場狀態 |
| 資金流向 | 資金流動分析 |
| 盤後總覽 | 收盤後市場總結 |
| 預測驗證 | 策略預測追蹤 |
| 技術分析 | K線圖與技術指標 |
| AI 智慧選股 | 多因子 AI 評分選股 |
| 社群輿情 | PTT / X 社群情緒分析 |

## 自動化

設定每日自動更新（macOS launchd）：

```bash
./scripts/setup_launchd.sh
```

## 授權

僅供個人學習研究使用。
