"""
投資組合共用工具函數
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from core.json_store import file_lock, save_json_atomic
from core.user_storage import DEFAULT_USER_ID, user_data_path

# 投資組合檔案路徑
PORTFOLIO_FILE = Path(__file__).parent.parent.parent / 'data' / 'portfolios.json'
PORTFOLIO_FILE.parent.mkdir(exist_ok=True)

# 成本價離群保護：單一持倉現價／成本比超過此倍數（或倒數）時，幾乎都是
# 成本價打錯或單位錯誤（例：把 160 元的股票成本存成 0.9），而非真實損益。
# 這類持倉的報酬率回 None，讓呼叫端顯示為「未知」而非荒謬的百分比，
# 也避免毒化整體損益彙總。實務上單筆持倉 ~1900% 報酬已是極端，足以判定異常。
PLAUSIBLE_PNL_RATIO = 20.0


def plausible_pnl_pct(current_price, cost_price) -> Optional[float]:
    """回傳合理的報酬率(%)；成本價缺失、非正或明顯異常（離群）時回 None。"""
    try:
        cp = float(cost_price)
        pr = float(current_price)
    except (TypeError, ValueError):
        return None
    if cp <= 0 or pr <= 0:
        return None
    ratio = pr / cp
    if ratio > PLAUSIBLE_PNL_RATIO or ratio < 1.0 / PLAUSIBLE_PNL_RATIO:
        return None
    return round((ratio - 1) * 100, 2)


def portfolio_file(user_id: str = DEFAULT_USER_ID) -> Path:
    """Return the portfolio store for one user."""
    return user_data_path(user_id, PORTFOLIO_FILE.name, PORTFOLIO_FILE.parent)


def load_portfolios(user_id: str = DEFAULT_USER_ID) -> Dict:
    """載入所有投資組合"""
    path = portfolio_file(user_id)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_portfolios(portfolios: Dict, user_id: str = DEFAULT_USER_ID) -> None:
    """儲存所有投資組合（atomic write，避免進程中斷毀檔）"""
    save_json_atomic(portfolio_file(user_id), portfolios)


def get_portfolio_names() -> List[str]:
    """取得所有投資組合名稱"""
    portfolios = load_portfolios()
    return list(portfolios.keys())


def create_portfolio(name: str) -> bool:
    """建立新投資組合"""
    with file_lock(PORTFOLIO_FILE):
        portfolios = load_portfolios()

        if name in portfolios:
            return False

        portfolios[name] = {
            'created_at': datetime.now().isoformat(),
            'holdings': [],
        }
        save_portfolios(portfolios)
        return True


def delete_portfolio(name: str) -> bool:
    """刪除投資組合"""
    with file_lock(PORTFOLIO_FILE):
        portfolios = load_portfolios()

        if name not in portfolios:
            return False

        del portfolios[name]
        save_portfolios(portfolios)
        return True


def add_holding(portfolio_name: str,
                stock_id: str,
                shares: int,
                cost_price: float,
                buy_date: Optional[str] = None) -> bool:
    """
    新增持股到投資組合

    Parameters:
    -----------
    portfolio_name : str
        投資組合名稱
    stock_id : str
        股票代號
    shares : int
        股數
    cost_price : float
        成本價
    buy_date : str, optional
        買入日期 (YYYY-MM-DD)

    Returns:
    --------
    bool
        是否成功
    """
    with file_lock(PORTFOLIO_FILE):
        portfolios = load_portfolios()

        if portfolio_name not in portfolios:
            return False

        if buy_date is None:
            buy_date = datetime.now().strftime('%Y-%m-%d')

        new_holding = {
            'stock_id': stock_id,
            'shares': shares,
            'cost_price': cost_price,
            'buy_date': buy_date,
        }

        portfolios[portfolio_name]['holdings'].append(new_holding)
        save_portfolios(portfolios)
        return True


def add_holdings_batch(portfolio_name: str,
                       stocks: List[str],
                       default_shares: int = 1000,
                       prices: Optional[Dict[str, float]] = None,
                       buy_date: Optional[str] = None) -> int:
    """
    批次新增多檔股票到投資組合

    Parameters:
    -----------
    portfolio_name : str
        投資組合名稱
    stocks : list
        股票代號列表
    default_shares : int
        預設股數
    prices : dict, optional
        股票代號 -> 價格 字典
    buy_date : str, optional
        買入日期 (YYYY-MM-DD)

    Returns:
    --------
    int
        成功新增的股票數量
    """
    with file_lock(PORTFOLIO_FILE):
        portfolios = load_portfolios()

        if portfolio_name not in portfolios:
            return 0

        if buy_date is None:
            buy_date = datetime.now().strftime('%Y-%m-%d')

        if prices is None:
            prices = {}

        count = 0
        existing_stocks = [h['stock_id'] for h in portfolios[portfolio_name]['holdings']]

        for stock_id in stocks:
            if stock_id in existing_stocks:
                continue

            cost_price = prices.get(stock_id, 0)

            new_holding = {
                'stock_id': stock_id,
                'shares': default_shares,
                'cost_price': cost_price,
                'buy_date': buy_date,
            }

            portfolios[portfolio_name]['holdings'].append(new_holding)
            count += 1

        save_portfolios(portfolios)
        return count


def remove_holding(portfolio_name: str, stock_id: str) -> bool:
    """從投資組合移除持股"""
    with file_lock(PORTFOLIO_FILE):
        portfolios = load_portfolios()

        if portfolio_name not in portfolios:
            return False

        holdings = portfolios[portfolio_name]['holdings']
        original_length = len(holdings)

        portfolios[portfolio_name]['holdings'] = [
            h for h in holdings if h['stock_id'] != stock_id
        ]

        if len(portfolios[portfolio_name]['holdings']) < original_length:
            save_portfolios(portfolios)
            return True

        return False


def get_portfolio_holdings(portfolio_name: str) -> List[Dict]:
    """取得投資組合的持股列表"""
    portfolios = load_portfolios()

    if portfolio_name not in portfolios:
        return []

    return portfolios[portfolio_name].get('holdings', [])


def get_portfolio_stock_ids(portfolio_name: str) -> List[str]:
    """取得投資組合的股票代號列表"""
    holdings = get_portfolio_holdings(portfolio_name)
    return [h['stock_id'] for h in holdings]
