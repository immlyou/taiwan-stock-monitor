"""API 層的共享單例物件

避免 api_server.py 與 routers 之間的循環 import。
所有 router 模組都從這裡取得共用 state。
"""
from __future__ import annotations

from pathlib import Path

from core.data_loader import DataLoader
from core.data_sources import MultiSourceDataProvider
from core.quote_provider import (
    FinLabCloseQuoteAdapter,
    FugleQuoteAdapter,
    QuoteService,
    TwseQuoteAdapter,
)


# 全域 DataLoader（程序生命週期內共用）
loader: DataLoader = DataLoader()

# 多源資料 Fallback（FinLab 額度超限時備援）
multi_source: MultiSourceDataProvider = MultiSourceDataProvider(loader)

# 即時報價統一入口：Fugle（有設定金鑰時）→ TWSE MIS → FinLab 日收盤。
# 各 router 共用同一個 15 秒 symbol cache，避免四個頁面各自輪詢造成 retry storm。
quote_service: QuoteService = QuoteService(
    live_adapters=[FugleQuoteAdapter(), TwseQuoteAdapter(multi_source)],
    fallback_adapter=FinLabCloseQuoteAdapter(loader),
    cache_ttl=15,
)

# 資料目錄（watchlists / portfolios / alerts 等 JSON 存放位置）
# 對應原 api_server.py 的 `Path(__file__).parent / "data"`（即 repo_root/data）
DATA_DIR: Path = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
