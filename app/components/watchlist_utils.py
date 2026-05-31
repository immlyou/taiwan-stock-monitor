"""
自選股共用工具函數
"""
import json
from pathlib import Path
from typing import Dict, List

# 自選股檔案路徑
WATCHLIST_FILE = Path(__file__).parent.parent.parent / 'data' / 'watchlists.json'
WATCHLIST_FILE.parent.mkdir(exist_ok=True)


def load_watchlists() -> Dict:
    """載入所有自選股清單"""
    if WATCHLIST_FILE.exists():
        try:
            with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_watchlists(watchlists: Dict) -> None:
    """儲存所有自選股清單"""
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(watchlists, f, ensure_ascii=False, indent=2, default=str)


def get_watchlist_names() -> List[str]:
    """取得所有自選股清單名稱"""
    watchlists = load_watchlists()
    return list(watchlists.keys())


def get_watchlist_stocks(watchlist_name: str) -> List[str]:
    """
    取得指定清單的股票代號列表

    支援兩種格式:
    - 新格式: {"清單名": {"stocks": ["2330", ...]}}
    - 舊格式: {"清單名": ["2330", ...]}
    """
    watchlists = load_watchlists()
    if watchlist_name not in watchlists:
        return []

    data = watchlists[watchlist_name]
    if isinstance(data, dict):
        return data.get('stocks', [])
    elif isinstance(data, list):
        return data
    return []


def get_all_watched_stocks() -> List[str]:
    """取得所有清單中的所有股票代號（去重）"""
    watchlists = load_watchlists()
    all_stocks = set()
    for name in watchlists:
        all_stocks.update(get_watchlist_stocks(name))
    return list(all_stocks)
