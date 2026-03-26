# -*- coding: utf-8 -*-
"""
Telegram 通知模組
================
發送台股戰情中心更新通知到 Telegram
"""

import os
import requests
from datetime import datetime

# Telegram 設定 — 從環境變數讀取，禁止硬編碼憑證
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 應用連結
CLOUD_URL = "https://taiwan-stock-monitor-rznlwkup7qvanohmtksqd4.streamlit.app/"


def send_update_notification(success=True, updated_count=0, error_count=0, details=None):
    """
    發送更新完成通知

    Args:
        success: 更新是否成功
        updated_count: 更新成功的資料數量
        error_count: 更新失敗的資料數量
        details: 額外詳細資訊
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    if success:
        message = f"✅ *台股戰情中心* 資料更新完成！\n\n"
        message += f"📊 更新時間：{now}\n"
        message += f"📈 成功更新：{updated_count} 項資料\n"
        if error_count > 0:
            message += f"⚠️ 更新失敗：{error_count} 項\n"
        message += f"\n🌐 [開啟戰情中心]({CLOUD_URL})"
    else:
        message = f"❌ *台股戰情中心* 資料更新失敗\n\n"
        message += f"⏰ 時間：{now}\n"
        if details:
            message += f"📝 錯誤：{details}\n"
        message += f"\n請檢查日誌：`cat ~/Documents/taiwan-stock-monitor/update.log`"

    return _send_telegram_message(message)


def send_market_summary(summary_data):
    """
    發送市場摘要通知

    Args:
        summary_data: 包含市場摘要的字典
    """
    now = datetime.now().strftime('%Y-%m-%d')

    message = f"📈 *台股戰情中心 - 每日摘要*\n"
    message += f"📅 {now}\n\n"

    if summary_data.get('index'):
        idx = summary_data['index']
        change_emoji = "🔺" if idx.get('change', 0) >= 0 else "🔻"
        message += f"📊 加權指數：{idx.get('value', 'N/A')} {change_emoji}{idx.get('change', 0)}%\n\n"

    if summary_data.get('top_gainers'):
        message += "🚀 *漲幅前 5*:\n"
        for stock in summary_data['top_gainers'][:5]:
            message += f"  • {stock.get('name', '')} ({stock.get('code', '')}) +{stock.get('change', 0)}%\n"
        message += "\n"

    if summary_data.get('top_losers'):
        message += "📉 *跌幅前 5*:\n"
        for stock in summary_data['top_losers'][:5]:
            message += f"  • {stock.get('name', '')} ({stock.get('code', '')}) {stock.get('change', 0)}%\n"
        message += "\n"

    message += f"🌐 [查看完整報告]({CLOUD_URL})"

    return _send_telegram_message(message)


def _send_telegram_message(message):
    """
    發送 Telegram 訊息
    """
    if not TELEGRAM_BOT_TOKEN:
        raise EnvironmentError(
            "環境變數 TELEGRAM_BOT_TOKEN 未設定。"
            "請在 .env 或執行環境中設定此變數，格式：TELEGRAM_BOT_TOKEN=<your_token>"
        )
    if not TELEGRAM_CHAT_ID:
        raise EnvironmentError(
            "環境變數 TELEGRAM_CHAT_ID 未設定。"
            "請在 .env 或執行環境中設定此變數，格式：TELEGRAM_CHAT_ID=<your_chat_id>"
        )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Telegram 通知已發送")
        return True
    except Exception as e:
        print(f"❌ Telegram 通知失敗: {e}")
        return False


if __name__ == '__main__':
    # 測試發送
    send_update_notification(success=True, updated_count=15, error_count=0)
