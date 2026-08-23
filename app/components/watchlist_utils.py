"""
自選股共用工具函數
"""
import json
from pathlib import Path
from typing import Dict, List

from core.json_store import save_json_atomic
from core.user_storage import DEFAULT_USER_ID, user_data_path

# 自選股檔案路徑
WATCHLIST_FILE = Path(__file__).parent.parent.parent / 'data' / 'watchlists.json'
WATCHLIST_FILE.parent.mkdir(exist_ok=True)


def watchlist_file(user_id: str = DEFAULT_USER_ID) -> Path:
    """Return the watchlist store for one user."""
    return user_data_path(user_id, WATCHLIST_FILE.name, WATCHLIST_FILE.parent)


def load_watchlists(user_id: str = DEFAULT_USER_ID) -> Dict:
    """載入所有自選股清單"""
    path = watchlist_file(user_id)
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_watchlists(watchlists: Dict, user_id: str = DEFAULT_USER_ID) -> None:
    """儲存所有自選股清單（atomic write，避免進程中斷毀檔）"""
    save_json_atomic(watchlist_file(user_id), watchlists)


def get_watchlist_names() -> List[str]:
    """取得所有自選股清單名稱"""
    watchlists = load_watchlists()
    return list(watchlists.keys())


def get_watchlist_stocks(
    watchlist_name: str, user_id: str = DEFAULT_USER_ID
) -> List[str]:
    """
    取得指定清單的股票代號列表

    支援兩種格式:
    - 新格式: {"清單名": {"stocks": ["2330", ...]}}
    - 舊格式: {"清單名": ["2330", ...]}
    """
    watchlists = load_watchlists(user_id)
    if watchlist_name not in watchlists:
        return []

    data = watchlists[watchlist_name]
    if isinstance(data, dict):
        return data.get('stocks', [])
    elif isinstance(data, list):
        return data
    return []


def get_all_watched_stocks(user_id: str = DEFAULT_USER_ID) -> List[str]:
    """取得所有清單中的所有股票代號（去重）"""
    watchlists = load_watchlists(user_id)
    all_stocks = set()
    for name in watchlists:
        all_stocks.update(get_watchlist_stocks(name, user_id))
    return list(all_stocks)
