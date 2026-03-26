"""
通知系統模組 - 支援 LINE Notify、Telegram 和 Email
"""
import os
import sys
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import NOTIFICATION_CONFIG
from core.exceptions import NotificationSendError, NotificationConfigError
from core.logging_config import get_logger

logger = get_logger('notification')


class NotificationChannel(ABC):
    """通知頻道抽象基礎類別"""

    @abstractmethod
    def send(self, title: str, message: str) -> bool:
        """
        發送通知

        Parameters:
        -----------
        title : str
            通知標題
        message : str
            通知內容

        Returns:
        --------
        bool
            是否發送成功
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """檢查是否已配置"""
        pass


class LineNotifyChannel(NotificationChannel):
    """
    LINE Notify 通知頻道

    使用 LINE Notify API 發送通知
    取得 Token: https://notify-bot.line.me/
    """

    API_URL = 'https://notify-api.line.me/api/notify'

    def __init__(self, token: Optional[str] = None):
        """
        Parameters:
        -----------
        token : str, optional
            LINE Notify Token，若未提供則從設定檔讀取
        """
        self.token = token or NOTIFICATION_CONFIG.get('line_notify', {}).get('token', '')

    def is_configured(self) -> bool:
        """檢查是否已配置 Token"""
        return bool(self.token)

    def send(self, title: str, message: str) -> bool:
        """
        發送 LINE 通知

        Parameters:
        -----------
        title : str
            通知標題
        message : str
            通知內容

        Returns:
        --------
        bool
            是否發送成功
        """
        if not self.is_configured():
            raise NotificationConfigError('LINE Notify', 'Token 未設定')

        try:
            import requests
        except ImportError:
            raise NotificationConfigError('LINE Notify', '請安裝 requests 套件: pip install requests')

        headers = {
            'Authorization': f'Bearer {self.token}',
        }

        data = {
            'message': f'\n\n{title}\n{"-" * 20}\n{message}',
        }

        try:
            response = requests.post(self.API_URL, headers=headers, data=data, timeout=10)

            if response.status_code == 200:
                logger.info(f'LINE 通知發送成功: {title}')
                return True
            else:
                error_msg = f'HTTP {response.status_code}: {response.text}'
                logger.error(f'LINE 通知發送失敗: {error_msg}')
                raise NotificationSendError('LINE Notify', error_msg)

        except requests.RequestException as e:
            logger.error(f'LINE 通知發送異常: {e}')
            raise NotificationSendError('LINE Notify', str(e))


class TelegramChannel(NotificationChannel):
    """
    Telegram Bot 通知頻道

    使用 Telegram Bot API 發送通知
    建立 Bot: https://t.me/BotFather
    取得 Chat ID: 發送訊息給 @userinfobot
    """

    API_URL = 'https://api.telegram.org/bot{token}/sendMessage'

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Parameters:
        -----------
        token : str, optional
            Telegram Bot Token，若未提供則從設定檔讀取
        chat_id : str, optional
            目標 Chat ID，若未提供則從設定檔讀取
        """
        telegram_config = NOTIFICATION_CONFIG.get('telegram', {})
        self.token = token or telegram_config.get('token', '')
        self.chat_id = chat_id or telegram_config.get('chat_id', '')

    def is_configured(self) -> bool:
        """檢查是否已配置 Token 和 Chat ID"""
        return bool(self.token and self.chat_id)

    def send(self, title: str, message: str) -> bool:
        """
        發送 Telegram 通知

        Parameters:
        -----------
        title : str
            通知標題
        message : str
            通知內容

        Returns:
        --------
        bool
            是否發送成功
        """
        if not self.is_configured():
            raise NotificationConfigError('Telegram', 'Bot Token 或 Chat ID 未設定')

        try:
            import requests
        except ImportError:
            raise NotificationConfigError('Telegram', '請安裝 requests 套件: pip install requests')

        url = self.API_URL.format(token=self.token)

        # 格式化訊息 (使用 Markdown)
        formatted_message = f"*{title}*\n{'─' * 20}\n{message}"

        data = {
            'chat_id': self.chat_id,
            'text': formatted_message,
            'parse_mode': 'Markdown',
        }

        try:
            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info(f'Telegram 通知發送成功: {title}')
                    return True
                else:
                    error_msg = result.get('description', '未知錯誤')
                    logger.error(f'Telegram 通知發送失敗: {error_msg}')
                    raise NotificationSendError('Telegram', error_msg)
            else:
                error_msg = f'HTTP {response.status_code}: {response.text}'
                logger.error(f'Telegram 通知發送失敗: {error_msg}')
                raise NotificationSendError('Telegram', error_msg)

        except requests.RequestException as e:
            logger.error(f'Telegram 通知發送異常: {e}')
            raise NotificationSendError('Telegram', str(e))

    def send_with_buttons(self, title: str, message: str,
                          buttons: List[Dict[str, str]]) -> bool:
        """
        發送帶有按鈕的 Telegram 通知

        Parameters:
        -----------
        title : str
            通知標題
        message : str
            通知內容
        buttons : list
            按鈕列表 [{'text': '按鈕文字', 'url': '連結'}]

        Returns:
        --------
        bool
            是否發送成功
        """
        if not self.is_configured():
            raise NotificationConfigError('Telegram', 'Bot Token 或 Chat ID 未設定')

        try:
            import requests
            import json
        except ImportError:
            raise NotificationConfigError('Telegram', '請安裝 requests 套件')

        url = self.API_URL.format(token=self.token)

        formatted_message = f"*{title}*\n{'─' * 20}\n{message}"

        # 建立 inline keyboard
        inline_keyboard = [[{'text': btn['text'], 'url': btn['url']}] for btn in buttons]

        data = {
            'chat_id': self.chat_id,
            'text': formatted_message,
            'parse_mode': 'Markdown',
            'reply_markup': json.dumps({'inline_keyboard': inline_keyboard}),
        }

        try:
            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200 and response.json().get('ok'):
                logger.info(f'Telegram 通知發送成功 (含按鈕): {title}')
                return True
            else:
                raise NotificationSendError('Telegram', response.text)

        except requests.RequestException as e:
            logger.error(f'Telegram 通知發送異常: {e}')
            raise NotificationSendError('Telegram', str(e))


class EmailChannel(NotificationChannel):
    """
    Email 通知頻道

    使用 SMTP 發送郵件通知
    """

    def __init__(self,
                 smtp_server: Optional[str] = None,
                 smtp_port: Optional[int] = None,
                 sender: Optional[str] = None,
                 password: Optional[str] = None,
                 recipients: Optional[List[str]] = None):
        """
        Parameters:
        -----------
        smtp_server : str, optional
            SMTP 伺服器
        smtp_port : int, optional
            SMTP 端口
        sender : str, optional
            發送者郵箱
        password : str, optional
            郵箱密碼或應用程式密碼
        recipients : list, optional
            收件人列表
        """
        email_config = NOTIFICATION_CONFIG.get('email', {})

        self.smtp_server = smtp_server or email_config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = smtp_port or email_config.get('smtp_port', 587)
        self.sender = sender or email_config.get('sender', '')
        self.password = password or email_config.get('password', '')
        self.recipients = recipients or email_config.get('recipients', [])

    def is_configured(self) -> bool:
        """檢查是否已配置"""
        return all([self.sender, self.password, self.recipients])

    def send(self, title: str, message: str) -> bool:
        """
        發送郵件通知

        Parameters:
        -----------
        title : str
            郵件主題
        message : str
            郵件內容

        Returns:
        --------
        bool
            是否發送成功
        """
        if not self.is_configured():
            raise NotificationConfigError('Email', '郵件設定不完整')

        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = ', '.join(self.recipients)
            msg['Subject'] = f'[台股分析系統] {title}'

            # 郵件內容
            body = f"""
{title}
{'=' * 40}

{message}

---
此郵件由台股分析系統自動發送
時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # 發送郵件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.recipients, msg.as_string())

            logger.info(f'Email 通知發送成功: {title}')
            return True

        except smtplib.SMTPException as e:
            logger.error(f'Email 通知發送失敗: {e}')
            raise NotificationSendError('Email', str(e))


class NotificationManager:
    """
    通知管理器 - 統一管理所有通知頻道
    """

    def __init__(self):
        self.channels: Dict[str, NotificationChannel] = {}
        self._init_default_channels()

    def _init_default_channels(self):
        """初始化預設頻道"""
        # LINE Notify
        if NOTIFICATION_CONFIG.get('line_notify', {}).get('enabled', False):
            self.register_channel('line', LineNotifyChannel())

        # Telegram
        if NOTIFICATION_CONFIG.get('telegram', {}).get('enabled', False):
            self.register_channel('telegram', TelegramChannel())

        # Email
        if NOTIFICATION_CONFIG.get('email', {}).get('enabled', False):
            self.register_channel('email', EmailChannel())

    def register_channel(self, name: str, channel: NotificationChannel):
        """註冊通知頻道"""
        if channel.is_configured():
            self.channels[name] = channel
            logger.info(f'通知頻道已註冊: {name}')
        else:
            logger.warning(f'通知頻道 {name} 未配置，跳過註冊')

    def send(self, title: str, message: str, channels: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        發送通知到指定頻道

        Parameters:
        -----------
        title : str
            通知標題
        message : str
            通知內容
        channels : list, optional
            指定頻道列表，None 表示發送到所有頻道

        Returns:
        --------
        dict
            各頻道發送結果 {頻道名: 是否成功}
        """
        results = {}
        target_channels = channels or list(self.channels.keys())

        for channel_name in target_channels:
            if channel_name not in self.channels:
                logger.warning(f'通知頻道不存在: {channel_name}')
                results[channel_name] = False
                continue

            try:
                results[channel_name] = self.channels[channel_name].send(title, message)
            except NotificationSendError as e:
                logger.error(f'頻道 {channel_name} 發送失敗: {e}')
                results[channel_name] = False

        return results

    def send_daily_report(self, report_content: str):
        """發送每日報告"""
        title = f"台股每日選股報告 - {datetime.now().strftime('%Y-%m-%d')}"
        return self.send(title, report_content)

    def send_alert(self, alert_type: str, message: str):
        """發送警報通知"""
        title = f"[警報] {alert_type}"
        return self.send(title, message)


# 全域通知管理器實例
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """取得通知管理器單例"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def send_notification(title: str, message: str, channels: Optional[List[str]] = None) -> Dict[str, bool]:
    """
    快速發送通知的便利函數

    Parameters:
    -----------
    title : str
        通知標題
    message : str
        通知內容
    channels : list, optional
        指定頻道列表

    Returns:
    --------
    dict
        各頻道發送結果
    """
    manager = get_notification_manager()
    return manager.send(title, message, channels)
