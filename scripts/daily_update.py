#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日數據更新腳本

使用 FinLab API 自動下載並更新本地數據
可設定為 cron job 或 launchd 每日自動執行
"""
import os
import sys
import pickle
import logging
from datetime import datetime
from pathlib import Path

# 設定路徑
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR))

# 載入 .env 環境變數
from dotenv import load_dotenv
env_path = ROOT_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path)
    # 設定 FinLab API Token
    if os.getenv('FINLAB_API_TOKEN'):
        import finlab
        finlab.login(os.getenv('FINLAB_API_TOKEN'))

from config import DATA_DIR, DATA_FILES

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ROOT_DIR / 'update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def update_data():
    """
    更新所有數據
    """
    try:
        from finlab import data

        logger.info('開始更新數據...')

        # 數據對應表: FinLab API 名稱 -> 本地檔案名
        data_mapping = {
            'price:收盤價': 'price#收盤價.pickle',
            'price:開盤價': 'price#開盤價.pickle',
            'price:最高價': 'price#最高價.pickle',
            'price:最低價': 'price#最低價.pickle',
            'price:成交股數': 'price#成交股數.pickle',
            'etl:adj_close': 'etl#adj_close.pickle',
            'etl:market_value': 'etl#market_value.pickle',
            'etl:is_flagged_stock': 'etl#is_flagged_stock.pickle',
            'price_earning_ratio:本益比': 'price_earning_ratio#本益比.pickle',
            'price_earning_ratio:股價淨值比': 'price_earning_ratio#股價淨值比.pickle',
            'price_earning_ratio:殖利率(%)': 'price_earning_ratio#殖利率(%).pickle',
            'monthly_revenue:當月營收': 'monthly_revenue#當月營收.pickle',
            'monthly_revenue:去年同月增減(%)': 'monthly_revenue#去年同月增減(%).pickle',
            'monthly_revenue:上月比較增減(%)': 'monthly_revenue#上月比較增減(%).pickle',
            'benchmark_return:發行量加權股價報酬指數': 'benchmark_return#發行量加權股價報酬指數.pickle',
        }

        updated_count = 0
        error_count = 0

        for api_name, filename in data_mapping.items():
            try:
                logger.info(f'正在更新: {api_name}')

                # 使用 FinLab API 取得數據
                df = data.get(api_name)

                # 儲存到本地
                filepath = DATA_DIR / filename
                with open(filepath, 'wb') as f:
                    pickle.dump(df, f)

                logger.info(f'  ✓ 已更新: {filename}')
                updated_count += 1

            except Exception as e:
                logger.error(f'  ✗ 更新失敗 {api_name}: {e}')
                error_count += 1

        # 更新股票分類
        try:
            logger.info('正在更新: 股票分類')
            categories = data.get('security_categories')
            with open(DATA_DIR / 'security_categories.pickle', 'wb') as f:
                pickle.dump(categories, f)
            logger.info('  ✓ 已更新: security_categories.pickle')
            updated_count += 1
        except Exception as e:
            logger.error(f'  ✗ 更新失敗 security_categories: {e}')
            error_count += 1

        # 更新到期資訊
        expiry_info = {
            'last_update': datetime.now().isoformat(),
            'next_update': None,
        }
        with open(DATA_DIR / 'expiry.pkl', 'wb') as f:
            pickle.dump(expiry_info, f)

        logger.info(f'數據更新完成！成功: {updated_count}, 失敗: {error_count}')

        return updated_count, error_count

    except ImportError:
        logger.error('請先安裝 finlab 套件: pip install finlab')
        return 0, -1
    except Exception as e:
        logger.error(f'更新過程發生錯誤: {e}')
        return 0, -1


def run_daily_screening():
    """
    執行每日選股並產生報告
    """
    try:
        logger.info('開始執行每日選股...')

        from core.data_loader import get_loader
        from core.strategies import ValueStrategy, GrowthStrategy, MomentumStrategy, CompositeStrategy

        loader = get_loader()
        loader.clear_cache()  # 清除快取以載入最新數據

        data = {
            'close': loader.get('close'),
            'volume': loader.get('volume'),
            'pe_ratio': loader.get('pe_ratio'),
            'pb_ratio': loader.get('pb_ratio'),
            'dividend_yield': loader.get('dividend_yield'),
            'revenue_yoy': loader.get('revenue_yoy'),
            'revenue_mom': loader.get('revenue_mom'),
        }

        # 執行各策略
        strategies = {
            '價值投資': ValueStrategy(),
            '成長投資': GrowthStrategy(),
            '動能投資': MomentumStrategy(),
            '綜合策略': CompositeStrategy(),
        }

        results = {}
        for name, strategy in strategies.items():
            try:
                result = strategy.run(data)
                results[name] = {
                    'stocks': result.stocks[:20],  # 取前20檔
                    'count': len(result.stocks),
                }
                logger.info(f'{name}: 找到 {len(result.stocks)} 檔股票')
            except Exception as e:
                logger.error(f'{name} 選股失敗: {e}')

        # 產生報告
        report = generate_daily_report(results)

        # 儲存報告
        report_dir = ROOT_DIR / 'reports'
        report_dir.mkdir(exist_ok=True)

        report_file = report_dir / f'daily_report_{datetime.now().strftime("%Y%m%d")}.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f'每日報告已儲存: {report_file}')

        return results

    except Exception as e:
        logger.error(f'每日選股過程發生錯誤: {e}')
        return None


def generate_daily_report(results):
    """產生每日選股報告"""
    report = f"""
=====================================
        台股每日選股報告
        {datetime.now().strftime("%Y-%m-%d %H:%M")}
=====================================

"""

    for strategy_name, result in results.items():
        report += f"""
【{strategy_name}】
符合條件股票數: {result['count']}
推薦標的:
"""
        for i, stock in enumerate(result['stocks'][:10], 1):
            report += f"  {i}. {stock}\n"

        report += "\n"

    report += """
=====================================
        注意事項
=====================================
1. 以上選股結果僅供參考
2. 投資前請自行研究個股基本面
3. 過去績效不代表未來表現

此報告由系統自動產生
=====================================
"""

    return report


def send_notification(title: str, message: str) -> dict:
    """
    發送通知

    支援 LINE Notify 和 Email，根據 config.py 設定自動啟用

    Parameters:
    -----------
    title : str
        通知標題
    message : str
        通知內容

    Returns:
    --------
    dict
        發送結果 {頻道名: 是否成功}
    """
    try:
        from core.notification import send_notification as _send

        results = _send(title, message)

        if results:
            for channel, success in results.items():
                if success:
                    logger.info(f'通知發送成功: {channel}')
                else:
                    logger.warning(f'通知發送失敗: {channel}')
        else:
            logger.info('沒有啟用的通知頻道')

        return results

    except ImportError:
        logger.warning('通知模組未安裝，跳過通知')
        return {}
    except Exception as e:
        logger.error(f'發送通知時發生錯誤: {e}')
        return {}


def main():
    """主程式"""
    import argparse

    parser = argparse.ArgumentParser(description='台股數據每日更新腳本')
    parser.add_argument('--update-only', action='store_true',
                       help='只更新數據，不執行選股')
    parser.add_argument('--screen-only', action='store_true',
                       help='只執行選股，不更新數據')

    args = parser.parse_args()

    logger.info('=' * 50)
    logger.info('每日更新任務開始')
    logger.info('=' * 50)

    # 更新數據
    if not args.screen_only:
        updated, errors = update_data()
        if errors == -1:
            logger.error('數據更新失敗，請檢查 FinLab API 設定')

    # 執行選股
    results = None
    if not args.update_only:
        results = run_daily_screening()

    # 發送通知
    if results:
        try:
            # 產生通知內容
            notification_content = f"今日選股摘要:\n\n"
            for strategy_name, result in results.items():
                notification_content += f"【{strategy_name}】找到 {result['count']} 檔股票\n"
                if result['stocks'][:5]:
                    notification_content += f"  推薦: {', '.join(result['stocks'][:5])}\n"
            notification_content += f"\n詳細報告請查看 reports 資料夾"

            send_notification('每日選股完成', notification_content)
        except Exception as e:
            logger.warning(f'發送通知失敗: {e}')

    logger.info('=' * 50)
    logger.info('每日更新任務完成')
    logger.info('=' * 50)


if __name__ == '__main__':
    main()
