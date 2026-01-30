"""
數據載入模組 - 負責載入與快取所有 pickle 數據

支援兩種模式：
1. 本地模式：從 pickle 檔案載入（開發環境）
2. 雲端模式：透過 FinLab API 直接載入（Streamlit Cloud）
"""
import os
import pickle
from pathlib import Path
from typing import Dict, Optional, List
import pandas as pd
from threading import Lock

# 嘗試載入 streamlit (非必要)
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_DIR, DATA_FILES

# 判斷是否在 Streamlit Cloud 環境
def is_streamlit_cloud() -> bool:
    """判斷是否在 Streamlit Cloud 環境"""
    # Streamlit Cloud 設定了這個環境變數
    return os.getenv('STREAMLIT_SHARING_MODE') == 'streamlit' or \
           os.getenv('STREAMLIT_SERVER_HEADLESS') == 'true' or \
           not (DATA_DIR / 'price#收盤價.pickle').exists()

# FinLab API 數據名稱對應
FINLAB_DATA_MAPPING = {
    'close': 'price:收盤價',
    'open': 'price:開盤價',
    'high': 'price:最高價',
    'low': 'price:最低價',
    'volume': 'price:成交股數',
    'adj_close': 'etl:adj_close',
    'market_value': 'etl:market_value',
    'is_flagged': 'etl:is_flagged_stock',
    'pe_ratio': 'price_earning_ratio:本益比',
    'pb_ratio': 'price_earning_ratio:股價淨值比',
    'dividend_yield': 'price_earning_ratio:殖利率(%)',
    'monthly_revenue': 'monthly_revenue:當月營收',
    'revenue_yoy': 'monthly_revenue:去年同月增減(%)',
    'revenue_mom': 'monthly_revenue:上月比較增減(%)',
    'benchmark': 'benchmark_return:發行量加權股價報酬指數',
    'categories': 'security_categories',
    'foreign_investors': 'institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)',
    'investment_trust': 'institutional_investors_trading_summary:投信買賣超股數',
    'dealer': 'institutional_investors_trading_summary:自營商買賣超股數(自行買賣)',
    'foreign_holding': 'foreign_investors_shareholding:全體外資及陸資持股比率',
    'margin_buy': 'margin_transactions:融資今日餘額',
    'margin_sell': 'margin_transactions:融券今日餘額',
}

# 初始化 FinLab API（如果在雲端環境）
_finlab_initialized = False

def init_finlab():
    """初始化 FinLab API"""
    global _finlab_initialized
    if _finlab_initialized:
        return True

    try:
        import finlab

        # 優先使用 st.secrets，其次使用環境變數
        token = None
        if HAS_STREAMLIT:
            try:
                token = st.secrets.get('FINLAB_API_TOKEN')
            except Exception:
                pass

        if not token:
            token = os.getenv('FINLAB_API_TOKEN')

        if token:
            finlab.login(token)
            _finlab_initialized = True
            return True
        else:
            return False
    except Exception as e:
        print(f"FinLab 初始化失敗: {e}")
        return False


class DataCache:
    """
    全域數據快取 - 單例模式

    確保整個應用程式共享同一份快取，避免重複載入
    """
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._cache = {}
                    cls._instance._load_times = {}  # 記錄載入時間
        return cls._instance

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """取得快取數據"""
        return self._cache.get(key)

    def set(self, key: str, value: pd.DataFrame):
        """設定快取數據"""
        import time
        self._cache[key] = value
        self._load_times[key] = time.time()

    def has(self, key: str) -> bool:
        """檢查是否有快取"""
        return key in self._cache

    def clear(self):
        """清除所有快取"""
        self._cache.clear()
        self._load_times.clear()

    def clear_key(self, key: str):
        """清除特定快取"""
        self._cache.pop(key, None)
        self._load_times.pop(key, None)

    def get_stats(self) -> Dict:
        """取得快取統計資訊"""
        return {
            'cached_keys': list(self._cache.keys()),
            'total_items': len(self._cache),
            'load_times': self._load_times.copy(),
        }


# 策略所需數據的映射
STRATEGY_DATA_REQUIREMENTS = {
    'value': ['close', 'pe_ratio', 'pb_ratio', 'dividend_yield'],
    'growth': ['close', 'revenue_yoy', 'revenue_mom', 'monthly_revenue'],
    'momentum': ['close', 'volume', 'high', 'low'],
    'composite': ['close', 'pe_ratio', 'pb_ratio', 'dividend_yield', 'revenue_yoy', 'revenue_mom', 'volume'],
}


class DataLoader:
    """數據載入器 - 提供統一的數據存取介面"""

    def __init__(self, data_dir: Optional[Path] = None, use_global_cache: bool = True):
        self.data_dir = data_dir or DATA_DIR
        self._use_global_cache = use_global_cache
        self._use_finlab_api = is_streamlit_cloud()

        # 使用全域快取或本地快取
        if use_global_cache:
            self._global_cache = DataCache()
            self._cache = None  # 不使用本地快取
        else:
            self._global_cache = None
            self._cache: Dict[str, pd.DataFrame] = {}

    def _load_from_finlab(self, data_key: str) -> pd.DataFrame:
        """從 FinLab API 載入數據"""
        if not init_finlab():
            raise RuntimeError("FinLab API 未初始化，請設定 FINLAB_API_TOKEN")

        from finlab import data

        api_name = FINLAB_DATA_MAPPING.get(data_key)
        if not api_name:
            raise KeyError(f"未知的數據鍵: {data_key}")

        df = data.get(api_name)

        # 確保是 DataFrame
        if isinstance(df, pd.DataFrame):
            return self._normalize_dataframe(df)
        elif isinstance(df, pd.Series):
            return df.to_frame()
        else:
            return pd.DataFrame(df)

    def _load_pickle(self, filename: str) -> pd.DataFrame:
        """載入 pickle 檔案"""
        filepath = self.data_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"找不到檔案: {filepath}")

        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        # 確保是 DataFrame
        if isinstance(data, pd.DataFrame):
            return self._normalize_dataframe(data)
        elif isinstance(data, pd.Series):
            return data.to_frame()
        else:
            return pd.DataFrame(data)

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """標準化 DataFrame 格式 - 以日期為 index"""
        if 'date' in df.columns:
            df = df.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
        return df

    def get(self, data_key: str, use_cache: bool = True) -> pd.DataFrame:
        """
        取得數據

        Parameters:
        -----------
        data_key : str
            數據鍵名，如 'close', 'pe_ratio' 等
        use_cache : bool
            是否使用快取

        Returns:
        --------
        pd.DataFrame
            數據 DataFrame，index 為日期，columns 為股票代號
        """
        # 優先檢查快取
        if use_cache:
            if self._use_global_cache and self._global_cache.has(data_key):
                return self._global_cache.get(data_key)
            elif not self._use_global_cache and data_key in self._cache:
                return self._cache[data_key]

        # 根據環境選擇載入方式
        if self._use_finlab_api:
            # 雲端模式：使用 FinLab API
            if data_key not in FINLAB_DATA_MAPPING:
                raise KeyError(f"未知的數據鍵: {data_key}. 可用的鍵: {list(FINLAB_DATA_MAPPING.keys())}")
            df = self._load_from_finlab(data_key)
        else:
            # 本地模式：從 pickle 載入
            if data_key not in DATA_FILES:
                raise KeyError(f"未知的數據鍵: {data_key}. 可用的鍵: {list(DATA_FILES.keys())}")
            filename = DATA_FILES[data_key]
            df = self._load_pickle(filename)

        # 存入快取
        if use_cache:
            if self._use_global_cache:
                self._global_cache.set(data_key, df)
            else:
                self._cache[data_key] = df

        return df

    def load_for_strategy(self, strategy_type: str) -> Dict[str, pd.DataFrame]:
        """
        只載入策略所需的數據

        Parameters:
        -----------
        strategy_type : str
            策略類型: 'value', 'growth', 'momentum', 'composite'

        Returns:
        --------
        Dict[str, pd.DataFrame]
            策略所需的數據字典
        """
        required_keys = STRATEGY_DATA_REQUIREMENTS.get(strategy_type, [])

        if not required_keys:
            # 如果策略類型未定義，載入所有基本數據
            required_keys = ['close', 'volume', 'pe_ratio', 'pb_ratio', 'dividend_yield']

        data = {}
        for key in required_keys:
            try:
                data[key] = self.get(key)
            except (FileNotFoundError, KeyError):
                # 忽略不存在的數據
                pass

        return data

    def preload_all(self) -> None:
        """預載入所有數據到快取"""
        for key in DATA_FILES.keys():
            try:
                self.get(key)
            except FileNotFoundError:
                pass  # 忽略不存在的檔案

    def get_stock_info(self) -> pd.DataFrame:
        """取得股票基本資訊 (代號、名稱、產業、市場)"""
        return self.get('categories')

    def get_stock_list(self) -> List[str]:
        """取得所有股票代號列表"""
        close = self.get('close')
        return [col for col in close.columns if col != 'date']

    def get_latest_date(self) -> pd.Timestamp:
        """取得最新數據日期"""
        close = self.get('close')
        return close.index.max()

    def get_benchmark(self) -> pd.Series:
        """取得大盤指數"""
        df = self.get('benchmark')
        if '發行量加權股價報酬指數' in df.columns:
            return df['發行量加權股價報酬指數']
        return df.iloc[:, 0]

    def clear_cache(self):
        """清除快取"""
        if self._use_global_cache:
            self._global_cache.clear()
        else:
            self._cache.clear()

    def get_cache_stats(self) -> Dict:
        """取得快取統計資訊"""
        if self._use_global_cache:
            return self._global_cache.get_stats()
        return {
            'cached_keys': list(self._cache.keys()),
            'total_items': len(self._cache),
        }


# Streamlit 快取版本
def _cache_decorator(func):
    """條件式快取裝飾器"""
    if HAS_STREAMLIT:
        return st.cache_data(ttl=3600)(func)
    return func


@_cache_decorator
def load_data(data_key: str) -> pd.DataFrame:
    """
    Streamlit 快取版本的數據載入函數

    Parameters:
    -----------
    data_key : str
        數據鍵名

    Returns:
    --------
    pd.DataFrame
        數據 DataFrame
    """
    loader = DataLoader()
    return loader.get(data_key, use_cache=False)


@_cache_decorator
def load_stock_info() -> pd.DataFrame:
    """載入股票基本資訊 (快取版)"""
    loader = DataLoader()
    return loader.get_stock_info()


@_cache_decorator
def load_benchmark() -> pd.Series:
    """載入大盤指數 (快取版)"""
    loader = DataLoader()
    return loader.get_benchmark()


# 活躍股票快取
_active_stocks_cache: Optional[Dict] = None


def get_active_stocks(days_threshold: int = 30, use_cache: bool = True) -> List[str]:
    """
    取得仍在交易的股票列表 (排除已下市股票)

    Parameters:
    -----------
    days_threshold : int
        判斷下市的天數門檻，預設 30 天內無交易視為下市
    use_cache : bool
        是否使用快取

    Returns:
    --------
    List[str]
        活躍股票代號列表
    """
    global _active_stocks_cache

    cache_key = f'active_{days_threshold}'

    # 檢查快取
    if use_cache and _active_stocks_cache is not None:
        if cache_key in _active_stocks_cache:
            return _active_stocks_cache[cache_key]

    loader = DataLoader()
    close = loader.get('close')

    latest_date = close.index.max()
    cutoff_date = latest_date - pd.Timedelta(days=days_threshold)

    # 找出每支股票最後有效數據的日期
    active_stocks = []
    for col in close.columns:
        stock_data = close[col].dropna()
        if len(stock_data) > 0 and stock_data.index.max() >= cutoff_date:
            active_stocks.append(col)

    # 存入快取
    if _active_stocks_cache is None:
        _active_stocks_cache = {}
    _active_stocks_cache[cache_key] = active_stocks

    return active_stocks


def clear_active_stocks_cache():
    """清除活躍股票快取"""
    global _active_stocks_cache
    _active_stocks_cache = None


def is_stock_active(stock_id: str, days_threshold: int = 30) -> bool:
    """
    檢查股票是否仍在交易

    Parameters:
    -----------
    stock_id : str
        股票代號
    days_threshold : int
        判斷下市的天數門檻

    Returns:
    --------
    bool
        是否仍在交易
    """
    loader = DataLoader()
    close = loader.get('close')

    if stock_id not in close.columns:
        return False

    latest_date = close.index.max()
    cutoff_date = latest_date - pd.Timedelta(days=days_threshold)

    stock_data = close[stock_id].dropna()
    if len(stock_data) == 0:
        return False

    return stock_data.index.max() >= cutoff_date


def get_data_summary() -> Dict:
    """取得數據摘要資訊"""
    loader = DataLoader()

    try:
        close = loader.get('close')
        benchmark = loader.get_benchmark()
        active_stocks = get_active_stocks()

        # 取得加權指數 (TAIEX)
        taiex_index = None
        taiex_change = None
        try:
            from core.twse_api import get_taiex
            taiex_index, taiex_change, _ = get_taiex()
        except Exception:
            pass

        return {
            'total_stocks': len(active_stocks),  # 只顯示活躍股票數量
            'all_stocks': len(close.columns),    # 全部股票數量 (含已下市)
            'delisted_stocks': len(close.columns) - len(active_stocks),  # 已下市股票數量
            'date_range': f"{close.index.min().strftime('%Y-%m-%d')} ~ {close.index.max().strftime('%Y-%m-%d')}",
            'total_days': len(close),
            'latest_date': close.index.max().strftime('%Y-%m-%d'),
            'latest_benchmark': benchmark.iloc[-1] if len(benchmark) > 0 else None,
            'taiex_index': taiex_index,  # 加權指數
            'taiex_change': taiex_change,  # 加權指數漲跌幅
        }
    except Exception as e:
        return {'error': str(e)}


# 單例模式
_loader_instance: Optional[DataLoader] = None


def get_loader() -> DataLoader:
    """取得 DataLoader 單例"""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = DataLoader()
    return _loader_instance


def reset_loader() -> None:
    """重置 DataLoader 單例，強制下次重新建立"""
    global _loader_instance
    if _loader_instance is not None:
        _loader_instance.clear_cache()
    _loader_instance = None


def reset_all_caches() -> None:
    """
    重置所有快取 - 用於強制重新載入數據

    這個函數會清除：
    1. DataLoader 單例
    2. DataCache 全域快取
    3. 活躍股票快取
    """
    global _loader_instance, _active_stocks_cache

    # 清除 DataLoader 單例
    if _loader_instance is not None:
        _loader_instance.clear_cache()
    _loader_instance = None

    # 清除 DataCache 全域快取
    cache = DataCache()
    cache.clear()

    # 清除活躍股票快取
    _active_stocks_cache = None
