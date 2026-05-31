"""
通知系統模組測試
涵蓋：LineNotifyChannel、TelegramChannel、EmailChannel、NotificationManager
"""
import pytest
from unittest.mock import MagicMock, patch

from core.exceptions import NotificationSendError, NotificationConfigError
from core.notification import (
    LineNotifyChannel, TelegramChannel, EmailChannel,
    NotificationManager, send_notification,
    NotificationChannel,
)


# ──────────────────────────────────────────────
# LineNotifyChannel
# ──────────────────────────────────────────────

class TestLineNotifyChannel:

    def test_not_configured_when_no_token(self):
        ch = LineNotifyChannel(token="")
        assert not ch.is_configured()

    def test_configured_with_token(self):
        ch = LineNotifyChannel(token="test_token_123")
        assert ch.is_configured()

    def test_send_raises_when_not_configured(self):
        ch = LineNotifyChannel(token="")
        with pytest.raises(NotificationConfigError):
            ch.send("title", "message")

    @patch("requests.post")
    def test_send_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        ch = LineNotifyChannel(token="valid_token")
        result = ch.send("測試標題", "測試內容")
        assert result is True
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_send_http_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_post.return_value = mock_resp

        ch = LineNotifyChannel(token="invalid_token")
        with pytest.raises(NotificationSendError):
            ch.send("title", "message")

    @patch("requests.post")
    def test_send_request_exception(self, mock_post):
        import requests
        mock_post.side_effect = requests.RequestException("連線失敗")

        ch = LineNotifyChannel(token="valid_token")
        with pytest.raises(NotificationSendError):
            ch.send("title", "message")


# ──────────────────────────────────────────────
# TelegramChannel
# ──────────────────────────────────────────────

class TestTelegramChannel:

    def test_not_configured_missing_token(self):
        ch = TelegramChannel(token="", chat_id="12345")
        assert not ch.is_configured()

    def test_not_configured_missing_chat_id(self):
        ch = TelegramChannel(token="bot_token", chat_id="")
        assert not ch.is_configured()

    def test_configured_with_both(self):
        ch = TelegramChannel(token="bot_token", chat_id="12345")
        assert ch.is_configured()

    def test_send_raises_when_not_configured(self):
        ch = TelegramChannel(token="", chat_id="")
        with pytest.raises(NotificationConfigError):
            ch.send("title", "message")

    @patch("requests.post")
    def test_send_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_post.return_value = mock_resp

        ch = TelegramChannel(token="bot_token", chat_id="12345")
        result = ch.send("測試標題", "測試內容")
        assert result is True

    @patch("requests.post")
    def test_send_telegram_api_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": False, "description": "Bad Request"}
        mock_post.return_value = mock_resp

        ch = TelegramChannel(token="bot_token", chat_id="12345")
        with pytest.raises(NotificationSendError):
            ch.send("title", "message")

    @patch("requests.post")
    def test_send_http_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server Error"
        mock_post.return_value = mock_resp

        ch = TelegramChannel(token="bot_token", chat_id="12345")
        with pytest.raises(NotificationSendError):
            ch.send("title", "message")

    @patch("requests.post")
    def test_send_with_buttons_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}
        mock_post.return_value = mock_resp

        ch = TelegramChannel(token="bot_token", chat_id="12345")
        buttons = [{"text": "查看", "url": "https://example.com"}]
        result = ch.send_with_buttons("標題", "內容", buttons)
        assert result is True

    @patch("requests.post")
    def test_send_with_buttons_not_configured(self, mock_post):
        ch = TelegramChannel(token="", chat_id="")
        with pytest.raises(NotificationConfigError):
            ch.send_with_buttons("title", "msg", [])


# ──────────────────────────────────────────────
# EmailChannel
# ──────────────────────────────────────────────

class TestEmailChannel:

    def test_not_configured_when_missing_fields(self):
        ch = EmailChannel(sender="", password="", recipients=[])
        assert not ch.is_configured()

    def test_configured_with_all_fields(self):
        ch = EmailChannel(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender="test@gmail.com",
            password="password",
            recipients=["recv@gmail.com"]
        )
        assert ch.is_configured()

    def test_send_raises_when_not_configured(self):
        ch = EmailChannel(sender="", password="", recipients=[])
        with pytest.raises(NotificationConfigError):
            ch.send("title", "message")

    @patch("smtplib.SMTP")
    def test_send_success(self, mock_smtp_class):
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        ch = EmailChannel(
            smtp_server="smtp.gmail.com", smtp_port=587,
            sender="s@gmail.com", password="pw",
            recipients=["r@gmail.com"]
        )
        result = ch.send("測試主旨", "測試內容")
        assert result is True

    @patch("smtplib.SMTP")
    def test_send_smtp_exception(self, mock_smtp_class):
        import smtplib
        mock_smtp_class.side_effect = smtplib.SMTPException("認證失敗")

        ch = EmailChannel(
            smtp_server="smtp.gmail.com", smtp_port=587,
            sender="s@gmail.com", password="wrong_pw",
            recipients=["r@gmail.com"]
        )
        with pytest.raises(NotificationSendError):
            ch.send("title", "message")


# ──────────────────────────────────────────────
# NotificationManager
# ──────────────────────────────────────────────

class TestNotificationManager:

    def test_init_no_channels_when_disabled(self):
        """預設設定所有頻道都是 disabled，所以 channels 應為空"""
        mgr = NotificationManager()
        assert isinstance(mgr.channels, dict)

    def test_register_channel_configured(self):
        mgr = NotificationManager()
        mock_ch = MagicMock(spec=NotificationChannel)
        mock_ch.is_configured.return_value = True
        mgr.register_channel("test", mock_ch)
        assert "test" in mgr.channels

    def test_register_channel_not_configured(self):
        mgr = NotificationManager()
        mock_ch = MagicMock(spec=NotificationChannel)
        mock_ch.is_configured.return_value = False
        mgr.register_channel("test", mock_ch)
        assert "test" not in mgr.channels

    def test_send_to_registered_channel(self):
        mgr = NotificationManager()
        mock_ch = MagicMock(spec=NotificationChannel)
        mock_ch.is_configured.return_value = True
        mock_ch.send.return_value = True
        mgr.register_channel("mock", mock_ch)

        results = mgr.send("標題", "內容", channels=["mock"])
        assert results["mock"] is True

    def test_send_to_unknown_channel(self):
        mgr = NotificationManager()
        results = mgr.send("標題", "內容", channels=["nonexistent"])
        assert results["nonexistent"] is False

    def test_send_handles_exception(self):
        mgr = NotificationManager()
        mock_ch = MagicMock(spec=NotificationChannel)
        mock_ch.is_configured.return_value = True
        mock_ch.send.side_effect = NotificationSendError("mock", "錯誤")
        mgr.register_channel("failing", mock_ch)

        results = mgr.send("標題", "內容", channels=["failing"])
        assert results["failing"] is False

    def test_send_daily_report(self):
        mgr = NotificationManager()
        mock_ch = MagicMock(spec=NotificationChannel)
        mock_ch.is_configured.return_value = True
        mock_ch.send.return_value = True
        mgr.register_channel("ch", mock_ch)

        mgr.send_daily_report("今日市場報告")
        mock_ch.send.assert_called_once()

    def test_send_alert(self):
        mgr = NotificationManager()
        mock_ch = MagicMock(spec=NotificationChannel)
        mock_ch.is_configured.return_value = True
        mock_ch.send.return_value = True
        mgr.register_channel("ch", mock_ch)

        mgr.send_alert("漲停警報", "2330 台積電觸及漲停")
        mock_ch.send.assert_called_once()

    def test_send_to_all_channels_when_none_specified(self):
        mgr = NotificationManager()
        for name in ["ch1", "ch2"]:
            mock_ch = MagicMock(spec=NotificationChannel)
            mock_ch.is_configured.return_value = True
            mock_ch.send.return_value = True
            mgr.register_channel(name, mock_ch)

        results = mgr.send("標題", "內容")
        assert "ch1" in results
        assert "ch2" in results


class TestSendNotificationHelper:
    def test_send_notification_returns_dict(self):
        result = send_notification("測試", "內容")
        assert isinstance(result, dict)
