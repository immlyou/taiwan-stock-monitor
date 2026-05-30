#!/usr/bin/env python3
"""
每日預測驗證腳本

功能：
1. 每日收盤後自動驗證所有待驗證的預測
2. 產生驗證報告
3. 可設定排程自動執行

使用方式：
    python scripts/daily_verify.py              # 執行驗證
    python scripts/daily_verify.py --report     # 僅顯示報告
    python scripts/daily_verify.py --stats 30   # 顯示最近30天統計
"""
import argparse
from datetime import datetime


from core.data_loader import get_loader
from core.prediction_tracker import get_tracker, PredictionType, PredictionStatus


def run_verification():
    """執行預測驗證"""
    print("=" * 60)
    print(f"📊 預測驗證系統 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 載入資料
    print("\n⏳ 載入股價資料...")
    loader = get_loader()
    close = loader.get('close')
    print(f"   ✓ 載入完成，資料日期至 {close.index.max().strftime('%Y-%m-%d')}")

    # 取得追蹤器
    tracker = get_tracker()
    pending = tracker.get_pending_predictions()
    print(f"\n📋 待驗證預測: {len(pending)} 筆")

    if len(pending) == 0:
        print("   沒有待驗證的預測")
        return

    # 執行驗證
    print("\n🔍 開始驗證...")
    results = tracker.verify_predictions(close)

    # 顯示結果
    print(f"\n{'=' * 60}")
    print("📈 驗證結果摘要")
    print(f"{'=' * 60}")
    print(f"   驗證筆數: {results['verified_count']}")
    print(f"   ✅ 成功: {results['success_count']}")
    print(f"   ❌ 失敗: {results['failed_count']}")
    print(f"   ⏰ 過期: {results['expired_count']}")

    if results['verified_count'] > 0:
        success_rate = results['success_count'] / results['verified_count'] * 100
        print(f"\n   📊 本次驗證勝率: {success_rate:.1f}%")

    # 顯示詳細結果
    if results['details']:
        print(f"\n{'─' * 60}")
        print("詳細結果:")
        print(f"{'─' * 60}")
        for detail in results['details']:
            status_icon = '✅' if detail['status'] == 'success' else '❌'
            return_str = f"{detail['return']:+.2f}%" if detail['return'] else 'N/A'
            print(f"   {status_icon} {detail['stock']} [{detail['type']}] 報酬: {return_str}")


def show_report():
    """顯示驗證報告"""
    tracker = get_tracker()

    print("=" * 60)
    print("📊 預測驗證報告")
    print("=" * 60)

    # 待驗證
    pending = tracker.get_pending_predictions()
    print(f"\n⏳ 待驗證預測: {len(pending)} 筆")

    if pending:
        print(f"{'─' * 60}")
        for p in pending[:10]:  # 最多顯示10筆
            print(f"   • {p.stock_id} {p.stock_name}")
            print(f"     類型: {p.type} | 建立: {p.created_at[:10]} | 到期: {p.expire_date}")
            if p.type == PredictionType.TARGET_PRICE.value:
                print(f"     目標價: {p.target_price} (現價: {p.created_price})")
            elif p.type == PredictionType.DIRECTION.value:
                direction = '看漲 📈' if p.predicted_direction == 'up' else '看跌 📉'
                print(f"     方向: {direction}")
        if len(pending) > 10:
            print(f"   ... 還有 {len(pending) - 10} 筆")

    # 最近驗證結果
    recent_verified = tracker.get_recent_predictions(days=7)
    verified = [p for p in recent_verified if p.status in [PredictionStatus.SUCCESS.value, PredictionStatus.FAILED.value]]

    print(f"\n📋 最近7天已驗證: {len(verified)} 筆")
    if verified:
        success = sum(1 for p in verified if p.status == PredictionStatus.SUCCESS.value)
        print(f"   ✅ 成功: {success} | ❌ 失敗: {len(verified) - success}")
        print(f"   📊 勝率: {success / len(verified) * 100:.1f}%")


def show_statistics(days: int = 30):
    """顯示統計資料"""
    tracker = get_tracker()
    stats = tracker.get_statistics(days=days)

    print("=" * 60)
    print(f"📊 預測統計 (最近 {days} 天)")
    print("=" * 60)

    print("\n📈 總體統計")
    print(f"{'─' * 40}")
    print(f"   總預測數: {stats['total']}")
    print(f"   待驗證: {stats['pending']}")
    print(f"   ✅ 成功: {stats['success']}")
    print(f"   ❌ 失敗: {stats['failed']}")
    print(f"   ⏰ 過期: {stats['expired']}")
    print(f"\n   📊 整體勝率: {stats['success_rate']:.1f}%")
    print(f"   💰 平均報酬: {stats['avg_return']:+.2f}%")

    # 依類型統計
    if stats['by_type']:
        print("\n📋 依預測類型")
        print(f"{'─' * 40}")
        type_names = {
            'target_price': '目標價',
            'direction': '漲跌方向',
            'stock_pick': '選股勝率'
        }
        for ptype, data in stats['by_type'].items():
            if data['total'] > 0:
                print(f"   {type_names.get(ptype, ptype)}:")
                print(f"      總數: {data['total']} | 已驗證: {data['verified']} | 成功: {data['success']}")
                print(f"      勝率: {data['success_rate']:.1f}%")

    # 依來源統計
    if stats['by_source']:
        print("\n🏷️ 依策略來源")
        print(f"{'─' * 40}")
        for source, data in stats['by_source'].items():
            print(f"   {source}:")
            print(f"      總數: {data['total']} | 勝率: {data['success_rate']:.1f}% | 平均報酬: {data['avg_return']:+.2f}%")


def main():
    parser = argparse.ArgumentParser(description='每日預測驗證')
    parser.add_argument('--report', action='store_true', help='顯示驗證報告')
    parser.add_argument('--stats', type=int, nargs='?', const=30, help='顯示統計 (預設30天)')

    args = parser.parse_args()

    if args.report:
        show_report()
    elif args.stats:
        show_statistics(days=args.stats)
    else:
        run_verification()
        print("\n")
        show_statistics(days=30)


if __name__ == '__main__':
    main()
