#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
警報檢查腳本 - 載入本地數據後檢查所有啟用中的警報並發送通知
可設定為排程執行（由 launchd 或 cron job 呼叫）
"""
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# 設定路徑
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR))

# 載入 .env 環境變數
from dotenv import load_dotenv
env_path = ROOT_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path)

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ROOT_DIR / 'alerts.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='檢查台股警報並發送通知')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='只檢查警報，不實際發送通知',
    )
    args = parser.parse_args()

    logger.info('=' * 50)
    logger.info(f'開始檢查警報 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    if args.dry_run:
        logger.info('[dry-run 模式] 不會實際發送通知')
    logger.info('=' * 50)

    try:
        from core.data_loader import get_loader
        from core.alerts import check_alerts_and_notify, AlertEngine

        # 載入數據
        logger.info('載入本地數據...')
        loader = get_loader()
        data = {
            'close': loader.get('close'),
            'high': loader.get('high'),
            'low': loader.get('low'),
            'volume': loader.get('volume'),
        }
        logger.info('數據載入完成')

        # 先確認是否有啟用中的警報
        engine = AlertEngine()
        active_alerts = engine.get_active_alerts()
        if not active_alerts:
            logger.info('目前沒有啟用中的警報，跳過檢查')
            return

        logger.info(f'啟用中的警報: {len(active_alerts)} 個')

        # 檢查警報（dry-run 時不發送通知）
        send_notification = not args.dry_run
        triggered = check_alerts_and_notify(data, send_notification=send_notification)

        if triggered:
            logger.info(f'觸發 {len(triggered)} 個警報:')
            for result in triggered:
                logger.info(f'  [{result.alert_type}] {result.stock_id}: {result.message}')
            if args.dry_run:
                logger.info('[dry-run] 實際執行時會發送以上通知')
        else:
            logger.info('沒有警報被觸發')

    except Exception as e:
        logger.error(f'檢查警報時發生錯誤: {e}', exc_info=True)
        sys.exit(1)

    logger.info('=' * 50)
    logger.info('警報檢查完成')
    logger.info('=' * 50)


if __name__ == '__main__':
    main()
