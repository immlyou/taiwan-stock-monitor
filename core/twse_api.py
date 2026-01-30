# -*- coding: utf-8 -*-
"""
TWSE API 模組 - 從證交所取得加權指數
"""
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import pandas as pd
from functools import lru_cache
import urllib3

# 抑制 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 證交所 API 設定
TWSE_INDEX_URL = "https://www.twse.com.tw/exchangeReport/FMTQIK"
TWSE_DAILY_URL = "https://www.twse.com.tw/exchangeReport/MI_INDEX"
TWSE_MARGIN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
TWSE_STOCK_MARGIN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U"

# 快取設定
_taiex_cache: Dict[str, any] = {}
_margin_cache: Dict[str, any] = {}
_cache_ttl = 300  # 快取 5 分鐘


def _parse_twse_date(date_str: str) -> datetime:
    """解析民國年日期格式 (如 '114/01/24')"""
    parts = date_str.split('/')
    if len(parts) == 3:
        year = int(parts[0]) + 1911  # 民國年轉西元年
        month = int(parts[1])
        day = int(parts[2])
        return datetime(year, month, day)
    return None


def _parse_number(num_str: str) -> float:
    """解析數字字串，移除千分位符號"""
    if isinstance(num_str, (int, float)):
        return float(num_str)
    try:
        return float(num_str.replace(',', ''))
    except (ValueError, AttributeError):
        return None


def fetch_taiex_monthly(year: int = None, month: int = None) -> Optional[pd.DataFrame]:
    """
    從證交所取得月度加權指數資料

    Parameters:
    -----------
    year : int
        西元年，預設為當前年
    month : int
        月份，預設為當前月

    Returns:
    --------
    pd.DataFrame
        包含日期、收盤指數、漲跌的 DataFrame
    """
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month

    try:
        response = requests.get(
            TWSE_INDEX_URL,
            params={
                'response': 'json',
                'date': f'{year}{month:02d}01',
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json',
            },
            timeout=10,
            verify=False,  # 跳過 SSL 驗證
        )
        response.raise_for_status()
        data = response.json()

        if data.get('stat') != 'OK' or 'data' not in data:
            return None

        # 解析資料
        records = []
        for row in data['data']:
            # 欄位: 日期, 成交股數, 成交金額, 成交筆數, 發行量加權股價指數, 漲跌點數
            if len(row) >= 5:
                date = _parse_twse_date(row[0])
                close = _parse_number(row[4])
                change = _parse_number(row[5]) if len(row) > 5 else None

                if date and close:
                    records.append({
                        'date': date,
                        'close': close,
                        'change': change,
                    })

        if records:
            df = pd.DataFrame(records)
            df.set_index('date', inplace=True)
            return df

    except Exception as e:
        print(f"取得 TWSE 指數失敗: {e}")

    return None


def fetch_taiex_latest() -> Optional[Dict]:
    """
    取得最新加權指數

    Returns:
    --------
    Dict
        包含 index (指數), change (漲跌), change_pct (漲跌幅%), date (日期) 的字典
    """
    global _taiex_cache

    # 檢查快取
    cache_key = 'latest_taiex'
    if cache_key in _taiex_cache:
        cached_time, cached_data = _taiex_cache[cache_key]
        if datetime.now() - cached_time < timedelta(seconds=_cache_ttl):
            return cached_data

    try:
        # 嘗試取得當月資料
        today = datetime.now()
        df = fetch_taiex_monthly(today.year, today.month)

        if df is None or len(df) == 0:
            # 如果當月沒資料，嘗試上個月
            last_month = today.replace(day=1) - timedelta(days=1)
            df = fetch_taiex_monthly(last_month.year, last_month.month)

        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            latest_date = df.index[-1]

            # 計算漲跌幅
            change = latest.get('change', 0) or 0
            close = latest['close']
            prev_close = close - change if change else close
            change_pct = (change / prev_close * 100) if prev_close else 0

            result = {
                'index': close,
                'change': change,
                'change_pct': change_pct,
                'date': latest_date.strftime('%Y-%m-%d'),
            }

            # 存入快取
            _taiex_cache[cache_key] = (datetime.now(), result)
            return result

    except Exception as e:
        print(f"取得最新 TAIEX 失敗: {e}")

    return None


def fetch_taiex_realtime() -> Optional[Dict]:
    """
    取得即時加權指數 (盤中資料)

    Returns:
    --------
    Dict
        包含 index, change, change_pct, time 的字典
    """
    global _taiex_cache

    # 檢查快取 (即時資料快取 60 秒)
    cache_key = 'realtime_taiex'
    if cache_key in _taiex_cache:
        cached_time, cached_data = _taiex_cache[cache_key]
        if datetime.now() - cached_time < timedelta(seconds=60):
            return cached_data

    try:
        # 使用 MI_INDEX API 取得即時資料
        today = datetime.now()
        response = requests.get(
            TWSE_DAILY_URL,
            params={
                'response': 'json',
                'date': today.strftime('%Y%m%d'),
                'type': 'IND',
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json',
            },
            timeout=10,
            verify=False,  # 跳過 SSL 驗證
        )
        response.raise_for_status()
        data = response.json()

        if data.get('stat') != 'OK':
            # 可能是非交易日，改用歷史資料
            return fetch_taiex_latest()

        # 解析即時指數
        if 'data8' in data:
            for row in data['data8']:
                if '發行量加權股價指數' in row[0]:
                    close = _parse_number(row[1])
                    change = _parse_number(row[2])

                    if close:
                        prev_close = close - change if change else close
                        change_pct = (change / prev_close * 100) if prev_close else 0

                        result = {
                            'index': close,
                            'change': change,
                            'change_pct': change_pct,
                            'date': today.strftime('%Y-%m-%d'),
                            'time': data.get('date', ''),
                        }

                        _taiex_cache[cache_key] = (datetime.now(), result)
                        return result

    except Exception as e:
        print(f"取得即時 TAIEX 失敗: {e}")

    # 失敗時回傳歷史資料
    return fetch_taiex_latest()


def get_taiex() -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    取得加權指數的簡便函數

    Returns:
    --------
    Tuple[float, float, str]
        (指數, 漲跌幅%, 日期) 或 (None, None, None)
    """
    data = fetch_taiex_realtime()
    if data:
        return data['index'], data['change_pct'], data['date']
    return None, None, None


def clear_taiex_cache():
    """清除 TAIEX 快取"""
    global _taiex_cache
    _taiex_cache.clear()


# ============================================================
# 融資融券 API
# ============================================================

def fetch_stock_margin(stock_id: str, date: str = None, retry_days: int = 5) -> Optional[Dict]:
    """
    取得個股融資融券資料

    Parameters:
    -----------
    stock_id : str
        股票代號 (如 '2330')
    date : str
        日期 (格式: YYYYMMDD)，預設為當天
    retry_days : int
        如果當天無資料，往前回溯的天數

    Returns:
    --------
    Dict
        包含融資融券資料的字典:
        - margin_buy: 融資餘額 (張)
        - margin_sell: 融券餘額 (張)
        - margin_ratio: 券資比 (%)
        - margin_buy_change: 融資增減
        - margin_sell_change: 融券增減
        - date: 資料日期
    """
    global _margin_cache

    # 如果沒指定日期，嘗試回溯找到最近的交易日資料
    if date is None:
        for i in range(retry_days):
            try_date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
            result = _fetch_stock_margin_for_date(stock_id, try_date)
            if result:
                return result
        return None
    else:
        return _fetch_stock_margin_for_date(stock_id, date)


def _fetch_stock_margin_for_date(stock_id: str, date: str) -> Optional[Dict]:
    """
    取得指定日期的個股融資融券資料 (使用 MI_MARGN API)
    """
    global _margin_cache

    # 檢查快取
    cache_key = f'margin_{stock_id}_{date}'
    if cache_key in _margin_cache:
        cached_time, cached_data = _margin_cache[cache_key]
        if datetime.now() - cached_time < timedelta(seconds=_cache_ttl):
            return cached_data

    try:
        # 使用 MI_MARGN API 取得融資融券彙總
        response = requests.get(
            TWSE_MARGIN_URL,
            params={
                'response': 'json',
                'date': date,
                'selectType': 'ALL',
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json',
            },
            timeout=15,
            verify=False,
        )
        response.raise_for_status()
        data = response.json()

        if data.get('stat') == 'OK' and 'tables' in data:
            # 找到融資融券彙總表 (第二個 table)
            for table in data['tables']:
                if '融資融券彙總' in table.get('title', ''):
                    # 欄位: 代號, 名稱, 買進, 賣出, 現金償還, 前日餘額, 今日餘額, 次一營業日限額,
                    #       買進, 賣出, 現券償還, 前日餘額, 今日餘額, 次一營業日限額, 資券互抵, 註記
                    # 前8欄是融資，後8欄是融券
                    for row in table.get('data', []):
                        if len(row) > 0 and str(row[0]).strip() == stock_id:
                            # 融資資料 (欄位 2-7)
                            margin_buy_prev = _parse_number(row[5]) if len(row) > 5 else 0  # 前日餘額
                            margin_buy = _parse_number(row[6]) if len(row) > 6 else 0  # 今日餘額

                            # 融券資料 (欄位 8-13)
                            margin_sell_prev = _parse_number(row[11]) if len(row) > 11 else 0  # 前日餘額
                            margin_sell = _parse_number(row[12]) if len(row) > 12 else 0  # 今日餘額

                            margin_buy_change = margin_buy - margin_buy_prev if margin_buy and margin_buy_prev else 0
                            margin_sell_change = margin_sell - margin_sell_prev if margin_sell and margin_sell_prev else 0

                            # 計算券資比 (融券/融資 * 100)
                            margin_ratio = (margin_sell / margin_buy * 100) if margin_buy and margin_buy > 0 else 0

                            # 格式化日期
                            data_date = date[:4] + '-' + date[4:6] + '-' + date[6:8]

                            result = {
                                'margin_buy': int(margin_buy) if margin_buy else 0,
                                'margin_sell': int(margin_sell) if margin_sell else 0,
                                'margin_ratio': round(margin_ratio, 2),
                                'margin_buy_change': int(margin_buy_change),
                                'margin_sell_change': int(margin_sell_change),
                                'date': data_date,
                                'stock_id': stock_id,
                            }

                            # 存入快取
                            _margin_cache[cache_key] = (datetime.now(), result)
                            return result

    except Exception as e:
        print(f"取得個股融資融券失敗 ({stock_id}): {e}")

    return None


def fetch_margin_history(stock_id: str, days: int = 30) -> Optional[pd.DataFrame]:
    """
    取得個股融資融券歷史資料

    Parameters:
    -----------
    stock_id : str
        股票代號
    days : int
        回溯天數，預設 30 天

    Returns:
    --------
    pd.DataFrame
        包含歷史融資融券資料
    """
    records = []
    today = datetime.now()

    for i in range(days):
        date = (today - timedelta(days=i)).strftime('%Y%m%d')
        data = fetch_stock_margin(stock_id, date)
        if data:
            records.append({
                'date': data['date'],
                'margin_buy': data['margin_buy'],
                'margin_sell': data['margin_sell'],
                'margin_ratio': data['margin_ratio'],
            })

    if records:
        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)
        return df

    return None


def clear_margin_cache():
    """清除融資融券快取"""
    global _margin_cache
    _margin_cache.clear()


# 測試用
if __name__ == '__main__':
    print("測試 TWSE API...")

    # 測試取得最新指數
    latest = fetch_taiex_latest()
    if latest:
        print(f"最新加權指數: {latest['index']:,.2f}")
        print(f"漲跌: {latest['change']:+,.2f} ({latest['change_pct']:+.2f}%)")
        print(f"日期: {latest['date']}")
    else:
        print("無法取得最新指數")

    print()

    # 測試即時指數
    realtime = fetch_taiex_realtime()
    if realtime:
        print(f"即時加權指數: {realtime['index']:,.2f}")
        print(f"漲跌: {realtime['change']:+,.2f} ({realtime['change_pct']:+.2f}%)")
    else:
        print("無法取得即時指數")

    print()

    # 測試融資融券
    print("測試融資融券 API...")
    margin = fetch_stock_margin('2330')
    if margin:
        print(f"股票: {margin['stock_id']}")
        print(f"融資餘額: {margin['margin_buy']:,} 張")
        print(f"融券餘額: {margin['margin_sell']:,} 張")
        print(f"券資比: {margin['margin_ratio']:.2f}%")
        print(f"融資增減: {margin['margin_buy_change']:+,}")
        print(f"融券增減: {margin['margin_sell_change']:+,}")
        print(f"資料日期: {margin['date']}")
    else:
        print("無法取得融資融券資料")
