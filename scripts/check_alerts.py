#!/usr/bin/env python3
"""
警報檢查腳本 - 可設定為排程執行
"""
import sys
from pathlib import Path
from datetime import datetime

# 設定路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import get_loader
from core.alerts import check_alerts_and_notify
from core.logging_config import setup_logging, get_logger

# 設定日誌
setup_logging(log_file='alerts.log')
logger = get_logger(__name__)


def main():
    """主函數"""
    logger.info(f'開始檢查警報 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    try:
        # 載入數據
        loader = get_loader()
        data = {
            'close': loader.get('close'),
            'high': loader.get('high'),
            'low': loader.get('low'),
            'volume': loader.get('volume'),
        }

        # 檢查警報並發送通知
        triggered = check_alerts_and_notify(data, send_notification=True)

        if triggered:
            logger.info(f'觸發 {len(triggered)} 個警報:')
            for result in triggered:
                logger.info(f'  - {result.stock_id}: {result.message}')
        else:
            logger.info('沒有警報被觸發')

    except Exception as e:
        logger.error(f'檢查警報時發生錯誤: {e}')
        raise

    logger.info('警報檢查完成')


if __name__ == '__main__':
    main()
