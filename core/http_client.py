"""
HTTP 客戶端模組 - 包含重試機制
"""
import requests
import time
import logging
from typing import Optional, Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)


class RetryConfig:
    """重試配置"""
    def __init__(self,
                 max_retries: int = 3,
                 initial_delay: float = 1.0,
                 max_delay: float = 30.0,
                 exponential_base: float = 2.0,
                 retry_on_status: tuple = (429, 500, 502, 503, 504)):
        """
        初始化重試配置

        Parameters:
        -----------
        max_retries : int
            最大重試次數
        initial_delay : float
            初始延遲秒數
        max_delay : float
            最大延遲秒數
        exponential_base : float
            指數退避基數
        retry_on_status : tuple
            需要重試的 HTTP 狀態碼
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retry_on_status = retry_on_status


def retry_with_exponential_backoff(config: Optional[RetryConfig] = None):
    """
    指數退避重試裝飾器

    Parameters:
    -----------
    config : RetryConfig, optional
        重試配置
    """
    if config is None:
        config = RetryConfig()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    response = func(*args, **kwargs)

                    # 檢查是否需要重試
                    if hasattr(response, 'status_code'):
                        if response.status_code in config.retry_on_status:
                            if attempt < config.max_retries:
                                delay = min(
                                    config.initial_delay * (config.exponential_base ** attempt),
                                    config.max_delay
                                )
                                logger.warning(
                                    f'HTTP {response.status_code}，{delay:.1f} 秒後重試 '
                                    f'(第 {attempt + 1}/{config.max_retries} 次)'
                                )
                                time.sleep(delay)
                                continue

                    return response

                except requests.exceptions.RequestException as e:
                    last_exception = e

                    if attempt < config.max_retries:
                        delay = min(
                            config.initial_delay * (config.exponential_base ** attempt),
                            config.max_delay
                        )
                        logger.warning(
                            f'請求失敗: {e}，{delay:.1f} 秒後重試 '
                            f'(第 {attempt + 1}/{config.max_retries} 次)'
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f'請求失敗，已達最大重試次數: {e}')
                        raise

            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class HttpClient:
    """
    HTTP 客戶端，支援自動重試

    Usage:
    ------
    client = HttpClient()
    response = client.get('https://api.example.com/data')
    response = client.post('https://api.example.com/submit', json={'key': 'value'})
    """

    def __init__(self,
                 timeout: int = 30,
                 retry_config: Optional[RetryConfig] = None,
                 default_headers: Optional[Dict[str, str]] = None):
        """
        初始化 HTTP 客戶端

        Parameters:
        -----------
        timeout : int
            請求超時秒數
        retry_config : RetryConfig, optional
            重試配置
        default_headers : dict, optional
            預設請求頭
        """
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self.default_headers = default_headers or {}
        self.session = requests.Session()

    def _prepare_headers(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """合併請求頭"""
        merged = self.default_headers.copy()
        if headers:
            merged.update(headers)
        return merged

    @retry_with_exponential_backoff()
    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        """執行 HTTP 請求"""
        kwargs.setdefault('timeout', self.timeout)
        kwargs['headers'] = self._prepare_headers(kwargs.get('headers'))

        response = self.session.request(method, url, **kwargs)
        return response

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        GET 請求

        Parameters:
        -----------
        url : str
            請求 URL
        **kwargs
            其他 requests 參數

        Returns:
        --------
        requests.Response
            回應物件
        """
        return self._request('GET', url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """
        POST 請求

        Parameters:
        -----------
        url : str
            請求 URL
        **kwargs
            其他 requests 參數 (data, json, files 等)

        Returns:
        --------
        requests.Response
            回應物件
        """
        return self._request('POST', url, **kwargs)

    def put(self, url: str, **kwargs) -> requests.Response:
        """PUT 請求"""
        return self._request('PUT', url, **kwargs)

    def delete(self, url: str, **kwargs) -> requests.Response:
        """DELETE 請求"""
        return self._request('DELETE', url, **kwargs)

    def close(self):
        """關閉 session"""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 全域預設客戶端
_default_client: Optional[HttpClient] = None


def get_http_client() -> HttpClient:
    """取得全域 HTTP 客戶端"""
    global _default_client
    if _default_client is None:
        _default_client = HttpClient()
    return _default_client


def http_get(url: str, **kwargs) -> requests.Response:
    """快速 GET 請求"""
    return get_http_client().get(url, **kwargs)


def http_post(url: str, **kwargs) -> requests.Response:
    """快速 POST 請求"""
    return get_http_client().post(url, **kwargs)
