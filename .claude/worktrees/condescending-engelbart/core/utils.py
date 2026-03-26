"""
工具函數模組
"""
import pandas as pd
import re
from typing import Dict, List, Optional


def extract_stock_id(column_name: str) -> str:
    """
    從欄位名稱中提取股票代號

    Examples:
    - "1101 台泥" -> "1101"
    - "2330" -> "2330"
    - "0050" -> "0050"
    """
    if ' ' in column_name:
        return column_name.split(' ')[0]
    return column_name


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    標準化 DataFrame 欄位名稱，只保留股票代號
    """
    new_columns = [extract_stock_id(col) for col in df.columns]
    df = df.copy()
    df.columns = new_columns
    return df


def align_dataframes(dfs: Dict[str, pd.DataFrame],
                     normalize: bool = True) -> Dict[str, pd.DataFrame]:
    """
    對齊多個 DataFrame 的欄位名稱

    Parameters:
    -----------
    dfs : dict
        DataFrame 字典
    normalize : bool
        是否標準化欄位名稱 (只保留股票代號)

    Returns:
    --------
    dict
        對齊後的 DataFrame 字典
    """
    result = {}

    for key, df in dfs.items():
        if isinstance(df, pd.DataFrame):
            if normalize:
                result[key] = normalize_columns(df)
            else:
                result[key] = df.copy()
        else:
            result[key] = df

    return result


def get_common_stocks(dfs: Dict[str, pd.DataFrame]) -> List[str]:
    """
    取得多個 DataFrame 共同的股票代號
    """
    stock_sets = []

    for key, df in dfs.items():
        if isinstance(df, pd.DataFrame):
            cols = [extract_stock_id(col) for col in df.columns]
            stock_sets.append(set(cols))

    if not stock_sets:
        return []

    common = stock_sets[0]
    for s in stock_sets[1:]:
        common = common & s

    return list(common)


def find_nearest_date(df: pd.DataFrame, target_date: pd.Timestamp) -> pd.Timestamp:
    """
    找到 DataFrame 中最接近目標日期的日期
    """
    if target_date in df.index:
        return target_date

    # 找到小於等於目標日期的最大日期
    valid_dates = df.index[df.index <= target_date]
    if len(valid_dates) > 0:
        return valid_dates.max()

    # 如果沒有，取第一個日期
    return df.index.min()


def filter_trading_stocks(close: pd.DataFrame, date: pd.Timestamp,
                          min_price: float = 5.0,
                          min_volume: Optional[pd.Series] = None,
                          min_volume_value: float = 100) -> List[str]:
    """
    過濾可交易的股票

    Parameters:
    -----------
    close : pd.DataFrame
        收盤價
    date : pd.Timestamp
        日期
    min_price : float
        最低股價
    min_volume : pd.Series, optional
        成交量數據
    min_volume_value : float
        最低成交量

    Returns:
    --------
    list
        可交易的股票代號列表
    """
    if date not in close.index:
        date = find_nearest_date(close, date)

    prices = close.loc[date]
    valid = prices >= min_price
    valid = valid & prices.notna()

    if min_volume is not None and date in min_volume.index:
        vol = min_volume.loc[date]
        valid = valid & (vol >= min_volume_value)

    return valid[valid].index.tolist()
