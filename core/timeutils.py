"""台灣時區時間工具

Railway 容器跑 UTC（比台灣慢 8 小時），任何「盤中判斷」「日期邊界」
邏輯都不能用 naive datetime.now()，否則：
- 盤中判斷 09:00–13:30 會對到台灣 17:00–21:30
- 預測到期／驗證在 UTC 午夜前後會差一天

統一從這裡拿台北時間。
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def now_taipei() -> datetime:
    """目前的台北時間（timezone-aware）。"""
    return datetime.now(TAIPEI_TZ)


def today_taipei() -> date:
    """台北時區的今天日期。"""
    return now_taipei().date()
