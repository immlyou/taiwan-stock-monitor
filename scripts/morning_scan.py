#!/usr/bin/env python3
"""
每日晨報掃描腳本 - 可設定為排程執行

功能:
- 掃描多個 RSS Feed 新聞來源
- 分析利多/利空消息
- 識別熱門股票
- 發送通知 (LINE Notify / Telegram)

使用方式:
    python scripts/morning_scan.py
    python scripts/morning_scan.py --notify  # 發送通知
    python scripts/morning_scan.py --report  # 只產生報告不發送

排程設定 (crontab):
    0 8 * * 1-5 cd /path/to/finlab_db && python scripts/morning_scan.py --notify
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

# 設定路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import get_loader
from core.news_scanner import NewsScanner
from core.notification import get_notification_manager
from core.logging_config import setup_logging, get_logger

# 設定日誌
setup_logging(log_file='morning_scan.log')
logger = get_logger(__name__)


def format_morning_report(report: dict) -> str:
    """
    格式化晨報為文字訊息

    Parameters:
    -----------
    report : dict
        晨報數據

    Returns:
    --------
    str
        格式化後的文字訊息
    """
    lines = []
    lines.append(f"📰 每日晨報 - {datetime.now().strftime('%Y/%m/%d %H:%M')}")
    lines.append('=' * 30)
    lines.append('')

    # 摘要
    summary = report['summary']
    lines.append(f"📊 新聞統計")
    lines.append(f"  • 總新聞數: {summary['total_news']}")
    lines.append(f"  • 利多新聞: {summary['positive_count']}")
    lines.append(f"  • 利空新聞: {summary['negative_count']}")
    lines.append('')

    # 熱門股票
    if report['hot_stocks']:
        lines.append('🔥 熱門股票 (依提及次數)')
        for i, stock in enumerate(report['hot_stocks'][:5], 1):
            sentiment_icon = {
                'positive': '📈',
                'negative': '📉',
                'neutral': '➖'
            }.get(stock['sentiment'], '➖')
            lines.append(f"  {i}. {stock['stock_id']} ({stock['mention_count']}次) {sentiment_icon}")
        lines.append('')

    # 利多新聞
    if report['positive_news']:
        lines.append('📈 利多消息')
        for news in report['positive_news'][:3]:
            title = news['title'][:40] + '...' if len(news['title']) > 40 else news['title']
            stocks = ', '.join(news['stocks'][:2]) if news['stocks'] else ''
            lines.append(f"  • {title}")
            if stocks:
                lines.append(f"    → {stocks}")
        lines.append('')

    # 利空新聞
    if report['negative_news']:
        lines.append('📉 利空消息')
        for news in report['negative_news'][:3]:
            title = news['title'][:40] + '...' if len(news['title']) > 40 else news['title']
            stocks = ', '.join(news['stocks'][:2]) if news['stocks'] else ''
            lines.append(f"  • {title}")
            if stocks:
                lines.append(f"    → {stocks}")
        lines.append('')

    lines.append('─' * 30)
    lines.append('📱 詳細內容請查看系統晨報頁面')

    return '\n'.join(lines)


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='每日晨報掃描')
    parser.add_argument('--notify', action='store_true', help='發送通知')
    parser.add_argument('--report', action='store_true', help='只產生報告')
    parser.add_argument('--channels', nargs='+', help='指定通知頻道 (line, telegram, email)')

    args = parser.parse_args()

    logger.info('=' * 50)
    logger.info(f'開始每日晨報掃描 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    logger.info('=' * 50)

    try:
        # 載入股票資訊
        logger.info('載入股票資訊...')
        loader = get_loader()
        stock_info = loader.get_stock_info()

        # 初始化掃描器
        scanner = NewsScanner(stock_info)

        # 抓取所有新聞
        logger.info('開始抓取新聞...')
        news_items = scanner.fetch_all_feeds()
        logger.info(f'共抓取 {len(news_items)} 則新聞')

        # 產生晨報
        logger.info('產生晨報...')
        report = scanner.generate_morning_report()

        # 輸出摘要
        logger.info(f"新聞統計:")
        logger.info(f"  - 總數: {report['summary']['total_news']}")
        logger.info(f"  - 利多: {report['summary']['positive_count']}")
        logger.info(f"  - 利空: {report['summary']['negative_count']}")

        if report['hot_stocks']:
            logger.info("熱門股票:")
            for stock in report['hot_stocks'][:5]:
                logger.info(f"  - {stock['stock_id']}: {stock['mention_count']} 次提及")

        # 格式化訊息
        message = format_morning_report(report)

        if args.report:
            # 只印出報告
            print('\n' + message)
            logger.info('報告已產生 (未發送通知)')

        elif args.notify:
            # 發送通知
            logger.info('發送通知...')

            notification_manager = get_notification_manager()

            channels = args.channels if args.channels else None
            results = notification_manager.send(
                title='每日晨報',
                message=message,
                channels=channels
            )

            for channel, success in results.items():
                if success:
                    logger.info(f'  ✓ {channel}: 發送成功')
                else:
                    logger.warning(f'  ✗ {channel}: 發送失敗')

        else:
            # 預設行為：印出報告
            print('\n' + message)

        logger.info('晨報掃描完成')
        return 0

    except Exception as e:
        logger.error(f'晨報掃描失敗: {e}', exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
