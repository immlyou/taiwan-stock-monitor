"""
OpenClaw 台股戰情中心 Skill
============================
將此檔案放到 OpenClaw 所在電腦的 skills 目錄下。

安裝方式:
    1. 複製此檔案到 OpenClaw 的 skills 目錄
    2. 在 .env 設定 STOCK_API_URL 指向台股 API Server 的 IP
    3. 重啟 OpenClaw

使用範例 (在任何聊天平台對 OpenClaw 說):
    - "台股今天怎麼樣"
    - "查一下台積電"
    - "幫我選價值股"
    - "有什麼警報嗎"
    - "給我今天的晨報"
    - "本益比低於 12 殖利率大於 5% 的股票"
"""
import os
import requests

# ─── 設定 ───────────────────────────────────────────────
# 台股 API Server 位址（改成你那台電腦的 IP）
STOCK_API_URL = os.getenv("STOCK_API_URL", "http://localhost:8000")
STOCK_API_KEY = os.getenv("STOCK_API_KEY", "")

TIMEOUT = 15  # 請求超時秒數


# ─── HTTP 工具 ──────────────────────────────────────────

def _api_get(endpoint: str, params: dict = None) -> dict:
    """呼叫台股 API"""
    url = f"{STOCK_API_URL}{endpoint}"
    headers = {}
    if STOCK_API_KEY:
        headers["Authorization"] = f"Bearer {STOCK_API_KEY}"

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        return {"error": f"無法連線到台股 API ({STOCK_API_URL})，請確認 Server 是否啟動"}
    except requests.Timeout:
        return {"error": "台股 API 回應超時"}
    except Exception as e:
        return {"error": str(e)}


# ─── 格式化工具 ─────────────────────────────────────────

def _format_price_change(pct):
    """格式化漲跌幅"""
    if pct is None:
        return ""
    if pct > 0:
        return f"🔺 +{pct}%"
    elif pct < 0:
        return f"🔻 {pct}%"
    return f"➖ {pct}%"


def _format_stock_list(stocks, fields=None):
    """格式化股票清單"""
    if not stocks:
        return "（無符合條件的股票）"

    lines = []
    for i, s in enumerate(stocks, 1):
        parts = [f"{i}. {s['stock_id']}"]
        if "price" in s:
            parts.append(f"${s['price']}")
        if "change_pct" in s:
            parts.append(_format_price_change(s["change_pct"]))
        if "pe_ratio" in s:
            parts.append(f"PE:{s['pe_ratio']}")
        if "pb_ratio" in s:
            parts.append(f"PB:{s['pb_ratio']}")
        if "dividend_yield" in s:
            parts.append(f"殖利率:{s['dividend_yield']}%")
        if "revenue_yoy" in s:
            parts.append(f"YoY:{s['revenue_yoy']}%")
        if "revenue_mom" in s:
            parts.append(f"MoM:{s['revenue_mom']}%")
        if "volume_ratio" in s:
            parts.append(f"量比:{s['volume_ratio']}x")
        if "rsi" in s:
            parts.append(f"RSI:{s['rsi']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


# ─── 功能函數 (OpenClaw 會呼叫這些) ────────────────────

def market_summary() -> str:
    """取得市場總覽"""
    data = _api_get("/market/summary")
    if "error" in data:
        return f"❌ {data['error']}"

    msg = f"📊 *台股市場總覽* ({data.get('date', '')})\n"
    msg += "─" * 30 + "\n"

    if data.get("taiex_index"):
        msg += f"加權指數: {data['taiex_index']} {_format_price_change(data.get('taiex_change'))}\n"

    msg += f"\n上漲: {data.get('up_count', 0)} | 下跌: {data.get('down_count', 0)} | 平盤: {data.get('flat_count', 0)}\n"

    if data.get("top_gainers"):
        msg += "\n🚀 *漲幅排行*\n"
        for s in data["top_gainers"][:5]:
            msg += f"  {s['stock_id']} {_format_price_change(s['change_pct'])}\n"

    if data.get("top_losers"):
        msg += "\n📉 *跌幅排行*\n"
        for s in data["top_losers"][:5]:
            msg += f"  {s['stock_id']} {_format_price_change(s['change_pct'])}\n"

    return msg


def stock_query(stock_id: str) -> str:
    """查詢個股資訊"""
    # 基本資訊
    info = _api_get(f"/stock/{stock_id}")
    if "error" in info:
        return f"❌ {info['error']}"

    # 技術指標
    tech = _api_get(f"/stock/{stock_id}/technical")

    # 籌碼
    chip = _api_get(f"/stock/{stock_id}/chip")

    msg = f"📋 *{stock_id} 個股分析*\n"
    msg += "─" * 30 + "\n"
    msg += f"收盤價: ${info['latest_price']} {_format_price_change(info['change_pct'])}\n"
    msg += f"日期: {info['date']}\n\n"

    # 基本面
    msg += "📊 *基本面*\n"
    if info.get("pe_ratio"):
        msg += f"  本益比: {info['pe_ratio']}\n"
    if info.get("pb_ratio"):
        msg += f"  股價淨值比: {info['pb_ratio']}\n"
    if info.get("dividend_yield"):
        msg += f"  殖利率: {info['dividend_yield']}%\n"
    if info.get("revenue_yoy"):
        msg += f"  營收年增率: {info['revenue_yoy']}%\n"

    # 技術面
    if tech and "error" not in tech:
        msg += "\n📈 *技術面*\n"
        msg += f"  趨勢: {tech.get('trend', '—')}\n"
        msg += f"  RSI(14): {tech.get('rsi_14', '—')} ({tech.get('rsi_signal', '')})\n"
        msg += f"  MACD: {tech.get('macd', '—')}\n"
        msg += f"  MA5/20/60: {tech.get('sma_5', '—')}/{tech.get('sma_20', '—')}/{tech.get('sma_60', '—')}\n"

    # 籌碼
    if chip and "error" not in chip:
        msg += "\n🏦 *籌碼面*\n"
        for label in ("外資", "投信", "自營商"):
            if label in chip:
                total = chip[label]["total_shares"]
                emoji = "🟢" if total > 0 else "🔴" if total < 0 else "⚪"
                msg += f"  {emoji} {label}: {total:+,} 股\n"
        if chip.get("foreign_holding_pct"):
            msg += f"  外資持股: {chip['foreign_holding_pct']}%\n"

    return msg


def run_strategy(strategy_type: str, preset: str = "standard", top_n: int = 10) -> str:
    """執行選股策略"""
    strategy_names = {
        "value": "💎 價值投資",
        "growth": "🌱 成長投資",
        "momentum": "🚀 動能投資",
    }
    preset_names = {
        "conservative": "保守型",
        "standard": "標準型",
        "aggressive": "積極型",
    }

    data = _api_get(f"/strategy/{strategy_type}", {"preset": preset, "top_n": top_n})
    if "error" in data:
        return f"❌ {data['error']}"

    name = strategy_names.get(strategy_type, strategy_type)
    pname = preset_names.get(preset, preset)

    msg = f"{name} 選股結果 ({pname})\n"
    msg += f"📅 {data.get('date', '')}\n"
    msg += f"共 {data['total_matches']} 檔符合條件\n"
    msg += "─" * 30 + "\n"
    msg += _format_stock_list(data.get("stocks", []))

    return msg


def custom_screen(**kwargs) -> str:
    """自訂條件篩選"""
    data = _api_get("/screener", kwargs)
    if "error" in data:
        return f"❌ {data['error']}"

    filters = data.get("filters_applied", {})
    filter_desc = ", ".join(f"{k}={v}" for k, v in filters.items())

    msg = "🔍 *自訂篩選結果*\n"
    msg += f"條件: {filter_desc}\n"
    msg += f"共 {data['total_matches']} 檔符合\n"
    msg += "─" * 30 + "\n"
    msg += _format_stock_list(data.get("stocks", []))

    return msg


def check_alerts() -> str:
    """檢查警報"""
    data = _api_get("/alerts/check")
    if "error" in data:
        return f"❌ {data['error']}"

    if data["triggered_count"] == 0:
        return f"✅ 目前無觸發的警報 ({data['checked_at']})"

    msg = f"🔔 *警報通知* ({data['checked_at']})\n"
    msg += f"共 {data['triggered_count']} 項觸發\n"
    msg += "─" * 30 + "\n"

    for a in data["alerts"]:
        msg += f"⚠️ {a['stock_id']} - {a['type']}\n"
        msg += f"   {a['message']}\n\n"

    return msg


def morning_report() -> str:
    """取得每日晨報"""
    data = _api_get("/morning-report")
    if "error" in data:
        return f"❌ {data['error']}"

    msg = f"☀️ *每日晨報* ({data.get('date', '')})\n"
    msg += "═" * 30 + "\n\n"

    if data.get("taiex_index"):
        msg += f"📊 加權指數: {data['taiex_index']} {_format_price_change(data.get('taiex_change'))}\n"

    mkt = data.get("market", {})
    msg += f"漲: {mkt.get('up', 0)} | 跌: {mkt.get('down', 0)} | 平: {mkt.get('flat', 0)}\n\n"

    if data.get("top_gainers"):
        msg += "🚀 *漲幅前5*\n"
        for s in data["top_gainers"]:
            msg += f"  {s['stock_id']} {_format_price_change(s['change_pct'])}\n"
        msg += "\n"

    if data.get("top_losers"):
        msg += "📉 *跌幅前5*\n"
        for s in data["top_losers"]:
            msg += f"  {s['stock_id']} {_format_price_change(s['change_pct'])}\n"
        msg += "\n"

    strategies = data.get("strategies", {})
    if strategies:
        msg += "📋 *策略選股摘要*\n"
        for stype, sdata in strategies.items():
            names = {"value": "價值", "growth": "成長", "momentum": "動能"}
            name = names.get(stype, stype)
            top5 = ", ".join(sdata.get("top5", []))
            msg += f"  {name}: {sdata.get('total', 0)}檔 ({top5})\n"

    return msg


# ─── OpenClaw Skill 定義 ────────────────────────────────
# 以下是 OpenClaw 的 skill 配置格式

SKILL_CONFIG = {
    "name": "taiwan-stock",
    "description": "台股戰情中心 - 台灣股市即時分析、選股策略、籌碼分析",
    "version": "1.0.0",
    "author": "imchris",
    "triggers": [
        "台股", "股票", "選股", "台積電", "加權指數", "本益比",
        "殖利率", "籌碼", "法人", "晨報", "stock", "TWSE",
        "漲幅", "跌幅", "價值投資", "成長股", "動能",
    ],
    "commands": {
        "市場總覽": {
            "patterns": ["台股怎麼樣", "市場概況", "大盤", "今天行情", "市場總覽"],
            "handler": market_summary,
        },
        "查詢個股": {
            "patterns": ["查 {stock_id}", "查一下 {stock_id}", "{stock_id} 怎麼樣", "分析 {stock_id}"],
            "handler": stock_query,
        },
        "價值選股": {
            "patterns": ["價值投資", "選價值股", "高殖利率", "低本益比"],
            "handler": lambda: run_strategy("value"),
        },
        "成長選股": {
            "patterns": ["成長投資", "選成長股", "營收成長", "高成長"],
            "handler": lambda: run_strategy("growth"),
        },
        "動能選股": {
            "patterns": ["動能投資", "選動能股", "突破", "爆量"],
            "handler": lambda: run_strategy("momentum"),
        },
        "檢查警報": {
            "patterns": ["警報", "有警報嗎", "alert", "通知"],
            "handler": check_alerts,
        },
        "每日晨報": {
            "patterns": ["晨報", "每日報告", "morning report", "今日摘要"],
            "handler": morning_report,
        },
    },
}


# ─── 主程式 (測試用) ────────────────────────────────────

if __name__ == "__main__":
    print("🧪 測試台股 Skill 連線...\n")

    # 測試連線
    result = _api_get("/")
    if "error" in result:
        print(f"❌ 連線失敗: {result['error']}")
        print(f"   請確認 API Server 已啟動: {STOCK_API_URL}")
    else:
        print(f"✅ 已連線到: {result.get('name', 'Unknown')}")
        print(f"   版本: {result.get('version', '?')}\n")

        # 測試各功能
        print("=" * 50)
        print(morning_report())
        print("\n" + "=" * 50)
        print(market_summary())
