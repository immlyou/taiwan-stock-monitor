# -*- coding: utf-8 -*-
"""
即時報價模組 - 從證交所/櫃買中心取得個股即時報價

資料來源：
- 上市股票：台灣證券交易所 (TWSE)
- 上櫃股票：證券櫃檯買賣中心 (TPEx)
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
from dataclasses import dataclass
import urllib3
import json

# 抑制 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# API URLs
TWSE_REALTIME_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
TPEX_REALTIME_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
TWSE_ALL_STOCKS_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL"
TPEX_ALL_STOCKS_URL = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php"

# 快取
_quote_cache: Dict[str, Tuple[datetime, dict]] = {}
_cache_ttl = 10  # 即時報價快取 10 秒


@dataclass
class StockQuote:
    """個股即時報價"""
    stock_id: str           # 股票代號
    name: str               # 股票名稱
    price: float            # 成交價
    open: float             # 開盤價
    high: float             # 最高價
    low: float              # 最低價
    yesterday_close: float  # 昨收
    change: float           # 漲跌
    change_pct: float       # 漲跌幅 (%)
    volume: int             # 成交量 (股)
    volume_lots: int        # 成交量 (張)
    amount: float           # 成交金額
    bid_price: float        # 買價
    ask_price: float        # 賣價
    bid_volume: int         # 買量
    ask_volume: int         # 賣量
    time: str               # 成交時間
    is_trading: bool        # 是否盤中
    market: str             # 市場 (上市/上櫃)

    @property
    def is_up(self) -> bool:
        """是否上漲"""
        return self.change > 0

    @property
    def is_down(self) -> bool:
        """是否下跌"""
        return self.change < 0

    @property
    def is_limit_up(self) -> bool:
        """是否漲停"""
        if self.yesterday_close <= 0:
            return False
        limit = self.yesterday_close * 1.10
        return self.price >= limit * 0.999  # 容許小誤差

    @property
    def is_limit_down(self) -> bool:
        """是否跌停"""
        if self.yesterday_close <= 0:
            return False
        limit = self.yesterday_close * 0.90
        return self.price <= limit * 1.001  # 容許小誤差


def _parse_number(value, default=0) -> float:
    """解析數字，處理各種格式"""
    if value is None or value == '-' or value == '':
        return default
    try:
        if isinstance(value, (int, float)):
            return float(value)
        return float(str(value).replace(',', ''))
    except (ValueError, TypeError):
        return default


def _get_stock_code(stock_id: str) -> str:
    """
    取得查詢用的股票代碼格式

    上市: tse_{stock_id}.tw
    上櫃: otc_{stock_id}.tw
    """
    # 簡單判斷：6開頭或4位數以上通常是上櫃
    # 但這不準確，最好查表
    # 這裡先假設都是上市，API 會自動處理
    return f"tse_{stock_id}.tw"


def fetch_realtime_quote(stock_id: str, use_cache: bool = True) -> Optional[StockQuote]:
    """
    取得單一股票即時報價

    Parameters:
    -----------
    stock_id : str
        股票代號 (如 '2330')
    use_cache : bool
        是否使用快取

    Returns:
    --------
    StockQuote
        即時報價資料
    """
    quotes = fetch_realtime_quotes([stock_id], use_cache)
    return quotes.get(stock_id)


def fetch_realtime_quotes(stock_ids: List[str], use_cache: bool = True) -> Dict[str, StockQuote]:
    """
    批次取得多支股票即時報價

    Parameters:
    -----------
    stock_ids : List[str]
        股票代號列表
    use_cache : bool
        是否使用快取

    Returns:
    --------
    Dict[str, StockQuote]
        股票代號 -> 即時報價的字典
    """
    global _quote_cache

    results = {}
    stocks_to_fetch = []

    # 檢查快取
    if use_cache:
        for stock_id in stock_ids:
            if stock_id in _quote_cache:
                cached_time, cached_data = _quote_cache[stock_id]
                if datetime.now() - cached_time < timedelta(seconds=_cache_ttl):
                    results[stock_id] = cached_data
                    continue
            stocks_to_fetch.append(stock_id)
    else:
        stocks_to_fetch = list(stock_ids)

    if not stocks_to_fetch:
        return results

    try:
        # 建立查詢字串 (最多一次查 20 支)
        # 先嘗試上市
        tse_codes = [f"tse_{s}.tw" for s in stocks_to_fetch]
        otc_codes = [f"otc_{s}.tw" for s in stocks_to_fetch]

        # 同時查詢上市和上櫃
        all_codes = tse_codes + otc_codes

        # 分批查詢 (每批最多 20 支)
        batch_size = 20
        for i in range(0, len(all_codes), batch_size):
            batch_codes = all_codes[i:i+batch_size]
            ex_ch = '|'.join(batch_codes)

            response = requests.get(
                TWSE_REALTIME_URL,
                params={
                    'ex_ch': ex_ch,
                    'json': '1',
                    'delay': '0',
                    '_': int(datetime.now().timestamp() * 1000),
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'Referer': 'https://mis.twse.com.tw/stock/fibest.jsp',
                },
                timeout=10,
                verify=False,
            )
            response.raise_for_status()
            data = response.json()

            if 'msgArray' in data:
                for item in data['msgArray']:
                    stock_id = item.get('c', '')  # 股票代號
                    if not stock_id or stock_id not in stocks_to_fetch:
                        continue

                    # 解析報價
                    quote = _parse_quote_data(item)
                    if quote:
                        results[stock_id] = quote
                        _quote_cache[stock_id] = (datetime.now(), quote)

    except Exception as e:
        print(f"取得即時報價失敗: {e}")

    return results


def _parse_quote_data(item: dict) -> Optional[StockQuote]:
    """解析 API 回傳的報價資料"""
    try:
        stock_id = item.get('c', '')
        name = item.get('n', '')

        # 成交價
        price = _parse_number(item.get('z'))  # z: 成交價
        if price == 0:
            # 如果沒成交，用買價或昨收
            price = _parse_number(item.get('b', '').split('_')[0] if item.get('b') else 0)
            if price == 0:
                price = _parse_number(item.get('y'))  # y: 昨收

        # 其他價格
        open_price = _parse_number(item.get('o'))  # o: 開盤
        high = _parse_number(item.get('h'))  # h: 最高
        low = _parse_number(item.get('l'))  # l: 最低
        yesterday_close = _parse_number(item.get('y'))  # y: 昨收

        # 漲跌計算
        change = price - yesterday_close if yesterday_close > 0 else 0
        change_pct = (change / yesterday_close * 100) if yesterday_close > 0 else 0

        # 成交量 (v: 累積成交量，單位是股)
        volume = int(_parse_number(item.get('v', 0)))
        volume_lots = volume // 1000  # 轉換為張

        # 成交金額 (粗估)
        amount = price * volume if price and volume else 0

        # 五檔報價 (只取第一檔)
        bid_prices = item.get('b', '').split('_') if item.get('b') else []
        ask_prices = item.get('a', '').split('_') if item.get('a') else []
        bid_volumes = item.get('g', '').split('_') if item.get('g') else []
        ask_volumes = item.get('f', '').split('_') if item.get('f') else []

        bid_price = _parse_number(bid_prices[0]) if bid_prices else 0
        ask_price = _parse_number(ask_prices[0]) if ask_prices else 0
        bid_volume = int(_parse_number(bid_volumes[0])) if bid_volumes else 0
        ask_volume = int(_parse_number(ask_volumes[0])) if ask_volumes else 0

        # 成交時間
        trade_time = item.get('t', '')  # t: 成交時間 (HH:MM:SS)

        # 判斷市場
        ex = item.get('ex', 'tse')
        market = '上市' if ex == 'tse' else '上櫃'

        # 判斷是否盤中
        now = datetime.now()
        is_trading = (
            now.weekday() < 5 and  # 週一到週五
            datetime.strptime('09:00', '%H:%M').time() <= now.time() <= datetime.strptime('13:30', '%H:%M').time()
        )

        return StockQuote(
            stock_id=stock_id,
            name=name,
            price=price,
            open=open_price,
            high=high,
            low=low,
            yesterday_close=yesterday_close,
            change=change,
            change_pct=change_pct,
            volume=volume,
            volume_lots=volume_lots,
            amount=amount,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            time=trade_time,
            is_trading=is_trading,
            market=market,
        )

    except Exception as e:
        print(f"解析報價失敗: {e}")
        return None


def fetch_market_movers(market: str = 'all', limit: int = 10) -> Dict[str, List[StockQuote]]:
    """
    取得市場漲跌幅排行

    Parameters:
    -----------
    market : str
        'tse' (上市), 'otc' (上櫃), 'all' (全部)
    limit : int
        取得筆數

    Returns:
    --------
    Dict
        {'gainers': 漲幅排行, 'losers': 跌幅排行}
    """
    # 這個功能需要先取得所有股票列表
    # 暫時使用常見權值股做示範
    sample_stocks = [
        '2330', '2317', '2454', '2308', '2382',  # 台積電、鴻海、聯發科、台達電、廣達
        '2881', '2882', '2884', '2886', '2891',  # 金融股
        '1301', '1303', '1326', '2002', '2105',  # 傳產股
        '3711', '6669', '3037', '2603', '2609',  # 其他
    ]

    quotes = fetch_realtime_quotes(sample_stocks, use_cache=False)

    if not quotes:
        return {'gainers': [], 'losers': []}

    quote_list = list(quotes.values())

    # 排除沒有成交的
    quote_list = [q for q in quote_list if q.price > 0]

    # 漲幅排行
    gainers = sorted(quote_list, key=lambda x: x.change_pct, reverse=True)[:limit]

    # 跌幅排行
    losers = sorted(quote_list, key=lambda x: x.change_pct)[:limit]

    return {
        'gainers': gainers,
        'losers': losers,
    }


def clear_quote_cache():
    """清除報價快取"""
    global _quote_cache
    _quote_cache.clear()


def get_quote_summary(quotes: Dict[str, StockQuote]) -> Dict:
    """
    取得報價摘要統計

    Parameters:
    -----------
    quotes : Dict[str, StockQuote]
        報價字典

    Returns:
    --------
    Dict
        統計摘要
    """
    if not quotes:
        return {
            'total': 0,
            'up_count': 0,
            'down_count': 0,
            'flat_count': 0,
            'limit_up_count': 0,
            'limit_down_count': 0,
        }

    quote_list = list(quotes.values())

    return {
        'total': len(quote_list),
        'up_count': sum(1 for q in quote_list if q.is_up),
        'down_count': sum(1 for q in quote_list if q.is_down),
        'flat_count': sum(1 for q in quote_list if not q.is_up and not q.is_down),
        'limit_up_count': sum(1 for q in quote_list if q.is_limit_up),
        'limit_down_count': sum(1 for q in quote_list if q.is_limit_down),
    }


# 測試
if __name__ == '__main__':
    print("測試即時報價模組...")
    print()

    # 測試單支股票
    print("【台積電 (2330) 即時報價】")
    quote = fetch_realtime_quote('2330')
    if quote:
        print(f"股票: {quote.stock_id} {quote.name}")
        print(f"成交價: {quote.price:,.2f}")
        print(f"漲跌: {quote.change:+,.2f} ({quote.change_pct:+.2f}%)")
        print(f"開盤: {quote.open:,.2f} / 最高: {quote.high:,.2f} / 最低: {quote.low:,.2f}")
        print(f"成交量: {quote.volume_lots:,} 張")
        print(f"買價: {quote.bid_price:,.2f} / 賣價: {quote.ask_price:,.2f}")
        print(f"時間: {quote.time}")
        print(f"漲停: {quote.is_limit_up} / 跌停: {quote.is_limit_down}")
    else:
        print("無法取得報價")

    print()

    # 測試多支股票
    print("【批次查詢】")
    stocks = ['2330', '2317', '2454', '2881', '0050']
    quotes = fetch_realtime_quotes(stocks)
    for stock_id, q in quotes.items():
        arrow = '▲' if q.is_up else ('▼' if q.is_down else '─')
        print(f"{q.stock_id} {q.name}: {q.price:,.2f} {arrow} {q.change_pct:+.2f}%")
