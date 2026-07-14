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
from threading import Lock, RLock

# 載入 .env 檔案中的環境變數
try:
    from dotenv import load_dotenv
    # 從專案根目錄載入 .env
    _env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(_env_path)
except ImportError:
    pass

# 嘗試載入 streamlit (非必要)
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

from config import DATA_DIR, DATA_FILES, DATA_REGISTRY

# 判斷是否在 Streamlit Cloud 環境
def is_streamlit_cloud() -> bool:
    """判斷是否在 Streamlit Cloud 環境"""
    # Streamlit Cloud 設定了這個環境變數
    return os.getenv('STREAMLIT_SHARING_MODE') == 'streamlit' or \
           os.getenv('STREAMLIT_SERVER_HEADLESS') == 'true' or \
           not (DATA_DIR / 'price#收盤價.pickle').exists()

# FinLab API 數據名稱對應 - 從 DATA_REGISTRY 衍生，不再重複定義
FINLAB_DATA_MAPPING = {key: entry['finlab_key'] for key, entry in DATA_REGISTRY.items()}

# FinLab 流量追蹤（用於 /health 端點回報）
_finlab_usage_mb: float = 0.0
_finlab_quota_exceeded: bool = False
# 熔斷器：計數器與旗標所屬的台北日期。FinLab 額度每日（台灣午夜）重置，
# 跨日後自動歸零用量並關閉熔斷，讓新的一天重新嘗試。
_finlab_counter_date = None


def _reset_finlab_counters_if_new_day() -> None:
    """台灣跨日後重置 FinLab 用量與熔斷旗標（額度午夜重置）。

    熔斷器只在「同一天」短路：額度爆掉當天直接拒絕呼叫、不再浪費失敗請求；
    台灣午夜過後第一次呼叫會偵測到日期改變，歸零並放行重試。
    """
    global _finlab_usage_mb, _finlab_quota_exceeded, _finlab_counter_date
    from core.timeutils import today_taipei

    today = today_taipei()
    if _finlab_counter_date != today:
        _finlab_counter_date = today
        _finlab_usage_mb = 0.0
        _finlab_quota_exceeded = False


class FinLabQuotaExceededError(Exception):
    """FinLab API 每日額度超限"""
    pass


def _is_quota_error(e: Exception) -> bool:
    """判斷例外是否為 FinLab 每日額度超限。

    只比對額度錯誤的特定字樣（FinLab 實際訊息為 "Usage exceed 5000 MB" 類）。
    刻意不比對單獨的 "limit" / "exceed" / "5000"——
    "rate limit"、"timeout limit"、股號 5000 等無關錯誤會被誤判成額度超限，
    導致誤發告警或漏判後繼續打 API 燒額度。
    """
    if "quota" in type(e).__name__.lower():
        return True
    err_str = str(e).lower()
    return any(
        pattern in err_str
        for pattern in ("quota", "usage exceed", "5000 mb", "5000mb")
    )

# FinLab 快取 TTL（秒）：從環境變數讀取，預設 24 小時
# 設為 0 表示不使用記憶體快取（每次都重新下載）
FINLAB_CACHE_TTL: int = int(os.getenv("FINLAB_CACHE_TTL", "86400"))

# FinLab data.get() 短暫性錯誤重試設定。
# 只針對「網路抖動／逾時／5xx」這類可恢復錯誤做少量、短退避的重試，
# 避免單次抖動就直接失敗。次數刻意少、退避刻意短，以免拖長 API 延遲。
# 注意：額度超限（quota）絕不重試——快速失敗讓熔斷器接手。
FINLAB_RETRY_MAX: int = int(os.getenv("FINLAB_RETRY_MAX", "3"))
FINLAB_RETRY_INITIAL_DELAY: float = float(os.getenv("FINLAB_RETRY_INITIAL_DELAY", "0.5"))
FINLAB_RETRY_MAX_DELAY: float = float(os.getenv("FINLAB_RETRY_MAX_DELAY", "4.0"))
FINLAB_RETRY_BASE: float = 2.0


def _is_transient_finlab_error(e: Exception) -> bool:
    """判斷例外是否為 FinLab 下載的「短暫性錯誤」（值得重試）。

    只涵蓋網路層可恢復的狀況：連線錯誤、逾時、以及 5xx 類伺服器錯誤。
    刻意排除額度超限（由 _is_quota_error 處理、絕不重試）與其他未知錯誤
    （直接往上拋，不浪費重試）。
    """
    # 額度錯誤永不視為短暫性（呼叫端會先判斷，這裡再加一層保險）。
    if _is_quota_error(e):
        return False

    # requests 連線／逾時類例外（finlab 底層用 requests）
    try:
        import requests
        if isinstance(e, (requests.exceptions.ConnectionError,
                          requests.exceptions.Timeout,
                          requests.exceptions.ChunkedEncodingError)):
            return True
        if isinstance(e, requests.exceptions.HTTPError):
            resp = getattr(e, "response", None)
            status = getattr(resp, "status_code", None)
            if status is not None and 500 <= status < 600:
                return True
            return False
    except ImportError:
        pass

    # 內建逾時／連線錯誤
    if isinstance(e, (TimeoutError, ConnectionError)):
        return True

    # 字樣比對（finlab 可能包成一般 Exception / RuntimeError）
    err_str = str(e).lower()
    transient_patterns = (
        "timeout", "timed out", "connection", "connection reset",
        "connection aborted", "temporarily unavailable", "try again",
        "502", "503", "504", "bad gateway", "service unavailable",
        "gateway timeout", "remote end closed",
    )
    return any(p in err_str for p in transient_patterns)

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
                    cls._instance._rw_lock = RLock()  # 讀寫操作專用鎖（可重入）
        return cls._instance

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """取得快取數據"""
        with self._rw_lock:
            return self._cache.get(key)

    def set(self, key: str, value: pd.DataFrame):
        """設定快取數據"""
        import time
        with self._rw_lock:
            self._cache[key] = value
            self._load_times[key] = time.time()

    def has(self, key: str, max_age: int = 3600) -> bool:
        """檢查是否有快取且未過期

        Parameters
        ----------
        key : str
            快取鍵名
        max_age : int
            最大存活秒數，預設 3600（1 小時）。設為 0 表示不檢查過期。
        """
        import time as _time
        with self._rw_lock:
            if key not in self._cache:
                return False
            if max_age <= 0:
                return True
            load_time = self._load_times.get(key, 0)
            return (_time.time() - load_time) < max_age

    def clear(self):
        """清除所有快取"""
        with self._rw_lock:
            self._cache.clear()
            self._load_times.clear()

    def clear_key(self, key: str):
        """清除特定快取"""
        with self._rw_lock:
            self._cache.pop(key, None)
            self._load_times.pop(key, None)

    def get_stats(self) -> Dict:
        """取得快取統計資訊"""
        with self._rw_lock:
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

        # 每個 data_key 一把下載鎖：避免多執行緒（cache_warmer 背景緒 vs 請求緒，或
        # market 端點 run_in_executor 卸載後的多請求緒）同時 cache-miss → 重複打 FinLab
        # 下載，浪費稀缺額度並可能誤觸額度熔斷。_download_locks_meta 保護鎖字典本身。
        self._download_locks: Dict[str, Lock] = {}
        self._download_locks_meta = Lock()

    def _finlab_get_with_retry(self, data, api_name: str):
        """對 finlab data.get() 做「短暫性錯誤」的指數退避重試。

        只重試網路抖動／逾時／5xx 這類可恢復錯誤（_is_transient_finlab_error），
        且重試次數少、退避短（FINLAB_RETRY_* 設定），避免拖長 API 延遲。

        重要：額度錯誤（quota）絕不重試——立即設熔斷旗標、發告警、
        raise FinLabQuotaExceededError，讓熔斷器快速接手。
        其他未知錯誤也不重試，直接往上拋。
        """
        global _finlab_quota_exceeded

        import logging
        import time as _time
        _log = logging.getLogger(__name__)

        last_exc = None
        for attempt in range(FINLAB_RETRY_MAX + 1):
            try:
                return data.get(api_name)
            except Exception as e:
                # 額度錯誤：絕不重試，快速失敗交給熔斷器（維持既有行為）。
                if _is_quota_error(e):
                    _finlab_quota_exceeded = True
                    _log.error("FinLab 額度超限: %s", e)
                    try:
                        from core.finlab_quota_alerter import get_alerter
                        get_alerter().notify_quota_exceeded(error=str(e))
                    except Exception as alert_err:
                        _log.warning("quota exceeded alert failed: %s", alert_err)
                    raise FinLabQuotaExceededError(str(e)) from e

                # 非短暫性錯誤：不重試，直接往上拋。
                if not _is_transient_finlab_error(e):
                    raise

                last_exc = e
                if attempt < FINLAB_RETRY_MAX:
                    delay = min(
                        FINLAB_RETRY_INITIAL_DELAY * (FINLAB_RETRY_BASE ** attempt),
                        FINLAB_RETRY_MAX_DELAY,
                    )
                    _log.warning(
                        "FinLab 下載短暫性錯誤: %s，%.1f 秒後重試（第 %d/%d 次）",
                        e, delay, attempt + 1, FINLAB_RETRY_MAX,
                    )
                    _time.sleep(delay)
                else:
                    _log.error("FinLab 下載失敗，已達最大重試次數（%d）: %s",
                               FINLAB_RETRY_MAX, e)
                    raise

        # 理論上不會走到這（迴圈內必 return 或 raise），保險起見。
        if last_exc is not None:
            raise last_exc

    def _load_from_finlab(self, data_key: str) -> pd.DataFrame:
        """從 FinLab API 載入數據，並累計流量計數器"""
        global _finlab_usage_mb, _finlab_quota_exceeded

        import logging
        _log = logging.getLogger(__name__)

        # 熔斷器：跨日重置後，若今天已知額度超限就直接拒絕，
        # 不再送出注定失敗的請求（FinLab 失敗仍可能計入流量、且徒增延遲）。
        _reset_finlab_counters_if_new_day()
        if _finlab_quota_exceeded:
            _log.warning("FinLab 熔斷器開啟（今日額度已超限），跳過下載: %s", data_key)
            raise FinLabQuotaExceededError(
                "FinLab API 今日額度已超限，已停止呼叫並改走備用資料來源（午夜重置後自動恢復）"
            )

        if not init_finlab():
            raise RuntimeError("FinLab API 未初始化，請設定 FINLAB_API_TOKEN")

        from finlab import data

        api_name = FINLAB_DATA_MAPPING.get(data_key)
        if not api_name:
            raise KeyError(f"未知的數據鍵: {data_key}")

        _log.info("FinLab API 下載: %s (%s)", data_key, api_name)
        try:
            df = self._finlab_get_with_retry(data, api_name)
            _finlab_quota_exceeded = False
        except FinLabQuotaExceededError:
            # _finlab_get_with_retry 內已處理（設旗標、發告警），直接往上拋給熔斷器。
            raise
        except Exception as e:
            if _is_quota_error(e):
                _finlab_quota_exceeded = True
                _log.error("FinLab 額度超限: %s", e)
                try:
                    from core.finlab_quota_alerter import get_alerter
                    get_alerter().notify_quota_exceeded(error=str(e))
                except Exception as alert_err:
                    _log.warning("quota exceeded alert failed: %s", alert_err)
                raise FinLabQuotaExceededError(str(e)) from e
            raise

        # 估算流量（DataFrame 記憶體大小近似 pickle 大小）
        try:
            if isinstance(df, pd.DataFrame):
                estimated_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
            else:
                estimated_mb = 0.1
            _finlab_usage_mb += estimated_mb
            _log.info("FinLab 累計流量: %.1f MB（本次 +%.1f MB）", _finlab_usage_mb, estimated_mb)
            # 主動告警：跨越 80% / 95% 門檻時觸發
            try:
                from core.finlab_quota_alerter import get_alerter
                get_alerter().check_usage(_finlab_usage_mb)
            except Exception as alert_err:
                _log.warning("quota usage alert check failed: %s", alert_err)
        except Exception:
            pass

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

    # ── FinLab 資料集的 Volume 持久化快取 ───────────────────────
    # 雲端模式重啟後，記憶體 DataCache 會清空，導致預熱重新向 FinLab 下載
    # 整個市場資料、燒掉每日額度。把下載結果落地到 Railway 持久 Volume
    # (data/finlab_cache/)，重啟後直接從磁碟讀，不再重打 FinLab。
    _FINLAB_DISK_CACHE_DIR = Path(__file__).parent.parent / 'data' / 'finlab_cache'

    def _finlab_disk_path(self, data_key: str) -> Path:
        return self._FINLAB_DISK_CACHE_DIR / f'{data_key}.pkl'

    def _load_finlab_disk_cache(self, data_key: str, ignore_ttl: bool = False) -> Optional[pd.DataFrame]:
        """讀取 Volume 上的持久化快取。

        ignore_ttl=False：僅在檔案新鮮（age < FINLAB_CACHE_TTL）時回傳。
        ignore_ttl=True ：忽略新鮮度（熔斷／額度超限時的 stale fallback）。
        讀不到或過期回傳 None。
        """
        import time as _time
        import logging
        path = self._finlab_disk_path(data_key)
        try:
            if not path.exists():
                return None
            if not ignore_ttl and FINLAB_CACHE_TTL > 0:
                age = _time.time() - path.stat().st_mtime
                if age >= FINLAB_CACHE_TTL:
                    return None
            with open(path, 'rb') as f:
                df = pickle.load(f)
            if isinstance(df, pd.DataFrame):
                return df
            return None
        except Exception as e:  # noqa: BLE001 — 快取讀取失敗不可阻斷主流程
            logging.getLogger(__name__).warning("讀取 FinLab 磁碟快取失敗 %s: %s", data_key, e)
            return None

    def _save_finlab_disk_cache(self, data_key: str, df: pd.DataFrame) -> None:
        """原子寫入 Volume 持久化快取（tmp + os.replace，中斷不留壞檔）。"""
        import logging
        try:
            self._FINLAB_DISK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path = self._finlab_disk_path(data_key)
            tmp_path = path.with_name(path.name + '.tmp')
            with open(tmp_path, 'wb') as f:
                pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
            tmp_path.replace(path)
        except Exception as e:  # noqa: BLE001 — 寫快取失敗不可阻斷主流程
            logging.getLogger(__name__).warning("寫入 FinLab 磁碟快取失敗 %s: %s", data_key, e)

    def clear_finlab_disk_cache(self, keys: Optional[List[str]] = None) -> None:
        """刪除 Volume 持久化快取，強制下次 get() 重新向 FinLab 下載。

        keys=None 清除全部；否則只清指定 keys。供 /refresh 等「強制更新」使用，
        避免清掉記憶體快取後又從磁碟讀回舊資料。
        """
        import logging
        try:
            if not self._FINLAB_DISK_CACHE_DIR.exists():
                return
            targets = (
                [self._finlab_disk_path(k) for k in keys]
                if keys is not None
                else list(self._FINLAB_DISK_CACHE_DIR.glob('*.pkl'))
            )
            for path in targets:
                path.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            logging.getLogger(__name__).warning("清除 FinLab 磁碟快取失敗: %s", e)

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """標準化 DataFrame 格式 - 以日期為 index，並保證遞增排序。

        下游大量依賴「.iloc[-1] / .tail(n) = 最新資料」，FinLab 回傳的
        date-indexed frame 沒有排序保證，這裡統一 sort_index 維持不變量。
        """
        if 'date' in df.columns:
            df = df.copy()
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
        if not df.index.is_monotonic_increasing:
            df = df.sort_index()
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
        # 優先檢查快取（雲端模式使用 FINLAB_CACHE_TTL，本地模式不過期）
        cache_max_age = FINLAB_CACHE_TTL if self._use_finlab_api else 0

        # 快路徑：命中快取直接回，不取鎖（常見情況、零競爭成本）
        if use_cache:
            hit = self._cache_lookup(data_key, cache_max_age)
            if hit is not None:
                return hit
            # cache-miss：取該 key 專屬下載鎖後 double-check 再下載，避免多執行緒重複下載。
            with self._download_lock_for(data_key):
                hit = self._cache_lookup(data_key, cache_max_age)
                if hit is not None:
                    return hit
                return self._load_body(data_key, use_cache=True)

        # use_cache=False：呼叫端明示要繞過快取，不取下載鎖、不寫快取。
        return self._load_body(data_key, use_cache=False)

    def _cache_lookup(self, data_key: str, cache_max_age) -> Optional[pd.DataFrame]:
        """查記憶體快取；命中回 DataFrame，否則回 None（不觸發下載）。"""
        if self._use_global_cache:
            if self._global_cache.has(data_key, max_age=cache_max_age):
                return self._global_cache.get(data_key)
        elif self._cache is not None and data_key in self._cache:
            return self._cache[data_key]
        return None

    def _download_lock_for(self, data_key: str) -> Lock:
        """取得某 data_key 專屬的下載鎖（首次使用時建立）。"""
        with self._download_locks_meta:
            lk = self._download_locks.get(data_key)
            if lk is None:
                lk = Lock()
                self._download_locks[data_key] = lk
            return lk

    def _load_body(self, data_key: str, use_cache: bool) -> pd.DataFrame:
        """實際載入 data_key（FinLab / 本地 pickle）並依 use_cache 寫入快取。

        呼叫端保證：use_cache=True 時已持有該 key 的下載鎖、且已 double-check 過快取。
        """
        # 根據環境選擇載入方式
        if self._use_finlab_api:
            # 雲端模式：使用 FinLab API
            if data_key not in FINLAB_DATA_MAPPING:
                raise KeyError(f"未知的數據鍵: {data_key}. 可用的鍵: {list(FINLAB_DATA_MAPPING.keys())}")

            # 記憶體 miss 時，先試 Volume 上的持久化快取（重啟後免重打 FinLab）。
            if use_cache:
                disk_df = self._load_finlab_disk_cache(data_key)
                if disk_df is not None:
                    if self._use_global_cache:
                        self._global_cache.set(data_key, disk_df)
                    else:
                        self._cache[data_key] = disk_df
                    return disk_df

            try:
                df = self._load_from_finlab(data_key)
            except FinLabQuotaExceededError:
                # 額度超限／熔斷開啟：退而求其次，供應磁碟上的舊快取（忽略 TTL），
                # 比整個失敗好。沒有任何磁碟快取時才往上拋。
                stale = self._load_finlab_disk_cache(data_key, ignore_ttl=True)
                if stale is not None:
                    import logging
                    logging.getLogger(__name__).warning(
                        "FinLab 額度超限，供應磁碟舊快取: %s", data_key
                    )
                    if use_cache:
                        if self._use_global_cache:
                            self._global_cache.set(data_key, stale)
                        else:
                            self._cache[data_key] = stale
                    return stale
                raise

            # 下載成功 → 落地到 Volume 持久化，供下次重啟使用。
            if use_cache:
                self._save_finlab_disk_cache(data_key, df)
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
        """取得大盤指數（含息報酬指數）"""
        df = self.get('benchmark')
        if '發行量加權股價報酬指數' in df.columns:
            return df['發行量加權股價報酬指數']
        return df.iloc[:, 0]

    def get_price_index(self) -> pd.Series:
        """取得發行量加權股價「價格」指數（一般看的大盤加權指數，非含息報酬指數）。

        FinLab 資料集 stock_index_price:收盤指數 是各指數的收盤值表，取其中
        「上市發行量加權股價指數」欄。取不到時回傳空 Series，由呼叫端決定降級。
        """
        try:
            df = self.get('taiex_price')
        except Exception:
            return pd.Series(dtype=float)
        if df is None or len(df) == 0:
            return pd.Series(dtype=float)
        for col in ('上市發行量加權股價指數', '發行量加權股價指數', '收盤指數'):
            if col in df.columns:
                return df[col].dropna()
        return df.iloc[:, 0].dropna()

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
    cache = DataCache()
    cache_key = f'_active_stocks_{days_threshold}'

    # 檢查 DataCache 快取
    if use_cache and cache.has(cache_key, max_age=0):
        return cache.get(cache_key)

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

    # 存入 DataCache
    cache.set(cache_key, active_stocks)

    return active_stocks


def clear_active_stocks_cache():
    """清除活躍股票快取"""
    cache = DataCache()
    # 取得所有 _active_stocks_* 開頭的快取鍵，透過公開方法刪除
    stats = cache.get_stats()
    keys_to_delete = [k for k in stats.get('cached_keys', []) if k.startswith('_active_stocks_')]
    for k in keys_to_delete:
        cache.clear_key(k)


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
    2. DataCache 全域快取（含活躍股票快取）
    3. Streamlit @st.cache_data 快取（若在 Streamlit 環境）
    """
    global _loader_instance

    # 清除 DataLoader 單例
    if _loader_instance is not None:
        _loader_instance.clear_cache()
    _loader_instance = None

    # 清除 DataCache 全域快取（_active_stocks_* 也一併清除）
    cache = DataCache()
    cache.clear()

    # 清除 Volume 持久化快取（強制重載時連磁碟層一起失效，否則會讀回舊資料）
    try:
        DataLoader().clear_finlab_disk_cache()
    except Exception:
        pass

    # 清除 Streamlit @st.cache_data 快取
    try:
        import streamlit as st
        st.cache_data.clear()
    except Exception:
        pass  # 非 Streamlit 環境（如 API server）正常跳過
