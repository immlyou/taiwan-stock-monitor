"""
FinLab API 額度主動告警

當估算的流量跨越 WARN/CRITICAL 門檻時，主動透過通知頻道告警（目前用 Telegram）。
- 每日自動重置門檻追蹤（避免隔日殘留狀態）
- 每個門檻每日最多發一次（避免洗版）
- 通知失敗不影響主流程（log 後吞掉）

FinLab 每日額度為 5000 MB；未設定 TELEGRAM_BOT_TOKEN 時降級為只打 log。
"""
from __future__ import annotations

import logging
import threading
from datetime import date
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DAILY_QUOTA_MB: float = 5000.0
WARN_PCT: float = 80.0
CRITICAL_PCT: float = 95.0

_THRESHOLDS = (WARN_PCT, CRITICAL_PCT)


def _default_sender(title: str, message: str) -> bool:
    """預設通知發送器：走 core.notification.send_notification

    失敗或未設定頻道時回傳 False，不拋錯。
    """
    try:
        from core.notification import send_notification

        results = send_notification(title, message)
        return any(results.values()) if results else False
    except Exception as e:
        logger.warning("FinLab quota alert send failed: %s", e)
        return False


class FinLabQuotaAlerter:
    """追蹤 FinLab 估算流量，跨越門檻時發送告警

    Parameters
    ----------
    sender : callable, optional
        接受 (title, message) -> bool 的通知函式。測試時可注入 mock。
        預設走 core.notification.send_notification（支援 Telegram / Email / LINE）。
    """

    def __init__(self, sender: Optional[Callable[[str, str], bool]] = None) -> None:
        self._sender = sender or _default_sender
        self._lock = threading.Lock()
        self._last_alerted_threshold: float = 0.0
        self._last_reset_date: Optional[date] = None
        self._quota_exceeded_alerted: bool = False

    def _maybe_reset(self, today: date) -> None:
        """跨日時重置門檻狀態（需在鎖內呼叫）"""
        if self._last_reset_date != today:
            self._last_reset_date = today
            self._last_alerted_threshold = 0.0
            self._quota_exceeded_alerted = False

    def check_usage(self, current_mb: float, today: Optional[date] = None) -> Optional[float]:
        """檢查當前用量，若跨越新門檻則發送告警

        Parameters
        ----------
        current_mb : float
            目前累計用量（MB）
        today : date, optional
            當前日期（測試可注入）。預設 date.today()。

        Returns
        -------
        float or None
            本次觸發告警的門檻百分比；未觸發則回傳 None。
        """
        today = today or date.today()
        pct = (current_mb / DAILY_QUOTA_MB) * 100

        with self._lock:
            self._maybe_reset(today)

            # 找出此次用量已跨越、且尚未告警過的最高門檻
            crossed = [t for t in _THRESHOLDS if pct >= t and t > self._last_alerted_threshold]
            if not crossed:
                return None

            highest = max(crossed)
            self._last_alerted_threshold = highest

        # 鎖外發送（避免 Telegram 連線延遲擋住其他 FinLab 呼叫）
        self._send_usage_alert(pct, current_mb, highest)
        return highest

    def notify_quota_exceeded(self, error: str = "", today: Optional[date] = None) -> bool:
        """當 FinLab 回傳額度超限錯誤時呼叫，發送 CRITICAL 告警

        每日僅發一次，避免 fallback 期間每次 API 呼叫都洗版。
        """
        today = today or date.today()
        with self._lock:
            self._maybe_reset(today)
            if self._quota_exceeded_alerted:
                return False
            self._quota_exceeded_alerted = True

        title = "🚨 FinLab API 額度已耗盡"
        message = (
            "FinLab 每日額度已耗盡，API Server 已自動切換多源 fallback"
            " (yfinance / TWSE / FinMind / Goodinfo)。\n"
            f"錯誤訊息: {error or 'N/A'}\n"
            "額度將於午夜 UTC 重置。"
        )
        try:
            self._sender(title, message)
        except Exception as e:
            logger.warning("quota_exceeded alert send failed: %s", e)
        return True

    def _send_usage_alert(self, pct: float, current_mb: float, threshold: float) -> None:
        if threshold >= CRITICAL_PCT:
            title = f"🚨 FinLab API 額度接近上限 ({pct:.1f}%)"
        else:
            title = f"⚠️ FinLab API 額度警告 ({pct:.1f}%)"

        message = (
            f"目前累計流量 {current_mb:.1f} MB / 5000 MB ({pct:.1f}%)\n"
            f"跨越 {threshold:.0f}% 門檻。\n"
            "到達 100% 會自動切換多源 fallback（yfinance/TWSE/FinMind）。"
        )
        try:
            sent = self._sender(title, message)
            if sent:
                logger.info("FinLab quota alert sent: %.1f%% (%.1f MB)", pct, current_mb)
            else:
                logger.warning(
                    "FinLab quota alert NOT sent (no channel configured)"
                    " — threshold %.0f%% crossed silently",
                    threshold,
                )
        except Exception as e:
            logger.warning("FinLab quota alert send raised: %s", e)


_alerter: Optional[FinLabQuotaAlerter] = None
_factory_lock = threading.Lock()


def get_alerter() -> FinLabQuotaAlerter:
    """取得全域 singleton alerter"""
    global _alerter
    if _alerter is None:
        with _factory_lock:
            if _alerter is None:
                _alerter = FinLabQuotaAlerter()
    return _alerter


def reset_for_testing() -> None:
    """測試專用：重置全域 singleton"""
    global _alerter
    _alerter = None
