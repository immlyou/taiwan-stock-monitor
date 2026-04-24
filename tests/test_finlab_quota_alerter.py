"""
測試 core/finlab_quota_alerter.py
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from core import finlab_quota_alerter as alerter_mod
from core.finlab_quota_alerter import (
    FinLabQuotaAlerter,
    DAILY_QUOTA_MB,
    WARN_PCT,
    CRITICAL_PCT,
    get_alerter,
    reset_for_testing,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_for_testing()
    yield
    reset_for_testing()


def _mb_at_pct(pct: float) -> float:
    return DAILY_QUOTA_MB * pct / 100


class TestCheckUsage:
    def test_below_warn_no_alert(self):
        sender = MagicMock(return_value=True)
        a = FinLabQuotaAlerter(sender=sender)
        assert a.check_usage(_mb_at_pct(50)) is None
        sender.assert_not_called()

    def test_cross_warn_triggers_once(self):
        sender = MagicMock(return_value=True)
        a = FinLabQuotaAlerter(sender=sender)
        assert a.check_usage(_mb_at_pct(85)) == WARN_PCT
        # 再次呼叫同樣百分比，不應重複告警
        assert a.check_usage(_mb_at_pct(85)) is None
        assert sender.call_count == 1

    def test_cross_critical_triggers(self):
        sender = MagicMock(return_value=True)
        a = FinLabQuotaAlerter(sender=sender)
        assert a.check_usage(_mb_at_pct(96)) == CRITICAL_PCT
        sender.assert_called_once()

    def test_warn_then_critical_triggers_twice(self):
        sender = MagicMock(return_value=True)
        a = FinLabQuotaAlerter(sender=sender)
        a.check_usage(_mb_at_pct(85))  # WARN
        a.check_usage(_mb_at_pct(97))  # CRITICAL
        assert sender.call_count == 2

    def test_skip_warn_if_jump_directly_to_critical(self):
        """從 0 直接跳到 97% 應該仍能告警（挑最高門檻）"""
        sender = MagicMock(return_value=True)
        a = FinLabQuotaAlerter(sender=sender)
        assert a.check_usage(_mb_at_pct(97)) == CRITICAL_PCT
        sender.assert_called_once()

    def test_daily_reset(self):
        sender = MagicMock(return_value=True)
        a = FinLabQuotaAlerter(sender=sender)

        today = date(2026, 4, 24)
        tomorrow = today + timedelta(days=1)

        a.check_usage(_mb_at_pct(96), today=today)
        assert sender.call_count == 1

        # 隔日用量重新歸零（現實中 FinLab 額度會重置）
        a.check_usage(_mb_at_pct(82), today=tomorrow)
        assert sender.call_count == 2  # 新一天的 WARN 再次告警

    def test_sender_exception_swallowed(self):
        """告警失敗不應影響呼叫者"""
        sender = MagicMock(side_effect=RuntimeError("smtp boom"))
        a = FinLabQuotaAlerter(sender=sender)
        # 不應拋錯
        a.check_usage(_mb_at_pct(96))

    def test_sender_returns_false_still_marks_threshold(self):
        """無頻道設定時 sender 回 False，仍視為已通知避免下一次又嘗試"""
        sender = MagicMock(return_value=False)
        a = FinLabQuotaAlerter(sender=sender)
        a.check_usage(_mb_at_pct(85))
        a.check_usage(_mb_at_pct(86))
        assert sender.call_count == 1


class TestNotifyQuotaExceeded:
    def test_sends_once_per_day(self):
        sender = MagicMock(return_value=True)
        a = FinLabQuotaAlerter(sender=sender)
        assert a.notify_quota_exceeded("quota used up") is True
        # 再次呼叫不應重發
        assert a.notify_quota_exceeded("again") is False
        assert sender.call_count == 1

    def test_resets_next_day(self):
        sender = MagicMock(return_value=True)
        a = FinLabQuotaAlerter(sender=sender)
        today = date(2026, 4, 24)
        tomorrow = today + timedelta(days=1)
        a.notify_quota_exceeded("x", today=today)
        a.notify_quota_exceeded("y", today=tomorrow)
        assert sender.call_count == 2

    def test_sender_exception_swallowed(self):
        sender = MagicMock(side_effect=RuntimeError("telegram down"))
        a = FinLabQuotaAlerter(sender=sender)
        assert a.notify_quota_exceeded("err") is True  # 不拋錯


class TestSingletonFactory:
    def test_singleton(self):
        assert get_alerter() is get_alerter()

    def test_reset_creates_new_instance(self):
        a = get_alerter()
        reset_for_testing()
        assert get_alerter() is not a


class TestDefaultSenderFallback:
    def test_missing_notification_module_swallowed(self, monkeypatch):
        """未設定任何通知頻道時，預設 sender 應回 False 而非拋錯"""
        from core.finlab_quota_alerter import _default_sender

        # 即使沒有頻道設定，_default_sender 應返回 bool 不應 raise
        result = _default_sender("title", "message")
        assert result in (True, False)
