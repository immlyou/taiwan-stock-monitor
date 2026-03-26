# OpenClaw 台股戰情中心 Skill

## 架構

```
┌──────────────────────┐         HTTP         ┌──────────────────────────┐
│  OpenClaw (龍蝦電腦)  │  ◄──────────────►  │  台股 API Server (本機)    │
│                      │    REST API          │                          │
│  taiwan_stock_skill  │    port 8000         │  api_server.py           │
│  ├─ 市場總覽         │                      │  ├─ /market/summary      │
│  ├─ 個股查詢         │                      │  ├─ /stock/{id}          │
│  ├─ 選股策略         │                      │  ├─ /strategy/{type}     │
│  ├─ 籌碼分析         │                      │  ├─ /screener            │
│  ├─ 警報檢查         │                      │  ├─ /alerts/check        │
│  └─ 每日晨報         │                      │  └─ /morning-report      │
└──────────────────────┘                      └──────────────────────────┘
     (另一台電腦)                                   (這台 Mac)
```

## 步驟 1：啟動 API Server（這台 Mac）

```bash
# 安裝 FastAPI
cd ~/Projects/stock/taiwan-stock-monitor
pip install fastapi uvicorn

# 啟動（綁定 0.0.0.0 讓區網可存取）
python api_server.py

# 或帶 API Key 保護
STOCK_API_KEY=your_secret_key python api_server.py
```

啟動後可在瀏覽器打開 `http://localhost:8000/docs` 測試 API。

## 步驟 2：設定 OpenClaw（龍蝦電腦）

1. 將 `taiwan_stock_skill.py` 複製到 OpenClaw 的 skills 目錄

2. 在 OpenClaw 的 `.env` 加入：
```env
# 改成這台 Mac 的區網 IP（執行 ifconfig 查看）
STOCK_API_URL=http://192.168.1.xxx:8000

# 如果有設定 API Key
STOCK_API_KEY=your_secret_key
```

3. 重啟 OpenClaw

## 步驟 3：使用

在任何聊天平台對 OpenClaw 說：

| 指令 | 範例 |
|------|------|
| 市場總覽 | "台股今天怎麼樣" |
| 個股查詢 | "查一下 2330"、"台積電怎麼樣" |
| 價值選股 | "幫我選價值股"、"高殖利率的股票" |
| 成長選股 | "營收成長最好的股票" |
| 動能選股 | "最近有突破的股票" |
| 自訂篩選 | "本益比低於 15 殖利率大於 4% 的股票" |
| 警報 | "有什麼警報嗎" |
| 晨報 | "給我今天的晨報" |

## 查找本機 IP

```bash
# macOS
ifconfig | grep "inet " | grep -v 127.0.0.1

# 通常是 192.168.x.x 或 10.x.x.x
```

## 防火牆

如果連不上，檢查 macOS 防火牆是否阻擋了 port 8000：
- 系統設定 → 網路 → 防火牆 → 允許 Python 連入
