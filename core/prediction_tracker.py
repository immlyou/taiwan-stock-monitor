"""
預測驗證系統 - 追蹤並驗證投資預測的準確度

功能：
1. 目標價達成追蹤 - 預測股票會漲到某個目標價，驗證是否在 N 天內達成
2. 漲跌方向追蹤 - 預測明天/本週會漲或跌，驗證方向是否正確
3. 選股勝率追蹤 - 追蹤選股策略選出的股票，N 天後報酬是否為正
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Literal
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

# 資料儲存路徑
DATA_DIR = Path(__file__).parent.parent / 'data'
PREDICTIONS_FILE = DATA_DIR / 'predictions.json'
VERIFICATION_LOG_FILE = DATA_DIR / 'verification_log.json'


class PredictionType(str, Enum):
    """預測類型"""
    TARGET_PRICE = 'target_price'      # 目標價達成
    DIRECTION = 'direction'             # 漲跌方向
    STOCK_PICK = 'stock_pick'          # 選股勝率


class PredictionStatus(str, Enum):
    """預測狀態"""
    PENDING = 'pending'                 # 等待驗證
    SUCCESS = 'success'                 # 預測成功
    FAILED = 'failed'                   # 預測失敗
    EXPIRED = 'expired'                 # 已過期（超過驗證期限）
    CANCELLED = 'cancelled'             # 已取消


@dataclass
class Prediction:
    """單一預測記錄"""
    id: str                             # 唯一識別碼
    type: str                           # 預測類型
    stock_id: str                       # 股票代號
    stock_name: str                     # 股票名稱
    created_at: str                     # 建立時間
    created_price: float                # 建立時的股價

    # 預測內容
    target_price: Optional[float] = None       # 目標價（用於 target_price 類型）
    predicted_direction: Optional[str] = None  # 預測方向：up/down（用於 direction 類型）
    expected_return: Optional[float] = None    # 預期報酬率（用於 stock_pick 類型）

    # 驗證設定
    verify_days: int = 5                       # 驗證天數（幾天內達成）
    expire_date: str = None                    # 到期日

    # 驗證結果
    status: str = 'pending'                    # 狀態
    verified_at: Optional[str] = None          # 驗證時間
    verified_price: Optional[float] = None     # 驗證時的股價
    actual_return: Optional[float] = None      # 實際報酬率
    highest_price: Optional[float] = None      # 期間最高價
    lowest_price: Optional[float] = None       # 期間最低價
    notes: Optional[str] = None                # 備註

    # 來源追蹤
    source: Optional[str] = None               # 來源（策略名稱、晨報等）
    strategy_params: Optional[Dict] = None     # 策略參數


class PredictionTracker:
    """預測追蹤器"""

    def __init__(self):
        self.predictions: List[Prediction] = []
        self.verification_log: List[Dict] = []
        self._load_data()

    def _load_data(self):
        """載入資料"""
        DATA_DIR.mkdir(exist_ok=True)

        # 載入預測記錄
        if PREDICTIONS_FILE.exists():
            try:
                with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.predictions = [Prediction(**p) for p in data]
            except Exception as e:
                print(f"載入預測記錄失敗: {e}")
                self.predictions = []

        # 載入驗證日誌
        if VERIFICATION_LOG_FILE.exists():
            try:
                with open(VERIFICATION_LOG_FILE, 'r', encoding='utf-8') as f:
                    self.verification_log = json.load(f)
            except Exception:
                self.verification_log = []

    def _save_data(self):
        """儲存資料"""
        DATA_DIR.mkdir(exist_ok=True)

        # 儲存預測記錄
        with open(PREDICTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump([asdict(p) for p in self.predictions], f, ensure_ascii=False, indent=2)

        # 儲存驗證日誌
        with open(VERIFICATION_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.verification_log, f, ensure_ascii=False, indent=2)

    def add_target_price_prediction(
        self,
        stock_id: str,
        stock_name: str,
        current_price: float,
        target_price: float,
        verify_days: int = 20,
        source: str = None,
        notes: str = None
    ) -> Prediction:
        """
        新增目標價預測

        Parameters:
        -----------
        stock_id : str - 股票代號
        stock_name : str - 股票名稱
        current_price : float - 目前股價
        target_price : float - 目標價
        verify_days : int - 幾天內達成（預設20天）
        source : str - 來源
        notes : str - 備註
        """
        now = datetime.now()
        expire_date = (now + timedelta(days=verify_days)).strftime('%Y-%m-%d')

        prediction = Prediction(
            id=str(uuid.uuid4())[:8],
            type=PredictionType.TARGET_PRICE.value,
            stock_id=stock_id,
            stock_name=stock_name,
            created_at=now.strftime('%Y-%m-%d %H:%M:%S'),
            created_price=current_price,
            target_price=target_price,
            verify_days=verify_days,
            expire_date=expire_date,
            source=source,
            notes=notes
        )

        self.predictions.append(prediction)
        self._save_data()
        return prediction

    def add_direction_prediction(
        self,
        stock_id: str,
        stock_name: str,
        current_price: float,
        direction: Literal['up', 'down'],
        verify_days: int = 1,
        source: str = None,
        notes: str = None
    ) -> Prediction:
        """
        新增漲跌方向預測

        Parameters:
        -----------
        stock_id : str - 股票代號
        stock_name : str - 股票名稱
        current_price : float - 目前股價
        direction : str - 預測方向 'up' 或 'down'
        verify_days : int - 幾天後驗證（預設1天=明天）
        source : str - 來源
        notes : str - 備註
        """
        now = datetime.now()
        expire_date = (now + timedelta(days=verify_days)).strftime('%Y-%m-%d')

        prediction = Prediction(
            id=str(uuid.uuid4())[:8],
            type=PredictionType.DIRECTION.value,
            stock_id=stock_id,
            stock_name=stock_name,
            created_at=now.strftime('%Y-%m-%d %H:%M:%S'),
            created_price=current_price,
            predicted_direction=direction,
            verify_days=verify_days,
            expire_date=expire_date,
            source=source,
            notes=notes
        )

        self.predictions.append(prediction)
        self._save_data()
        return prediction

    def add_stock_pick_prediction(
        self,
        stock_id: str,
        stock_name: str,
        current_price: float,
        expected_return: float = None,
        verify_days: int = 5,
        source: str = None,
        strategy_params: Dict = None,
        notes: str = None
    ) -> Prediction:
        """
        新增選股預測（追蹤選股策略的勝率）

        Parameters:
        -----------
        stock_id : str - 股票代號
        stock_name : str - 股票名稱
        current_price : float - 目前股價
        expected_return : float - 預期報酬率（可選）
        verify_days : int - 幾天後驗證報酬（預設5天）
        source : str - 策略來源
        strategy_params : Dict - 策略參數
        notes : str - 備註
        """
        now = datetime.now()
        expire_date = (now + timedelta(days=verify_days)).strftime('%Y-%m-%d')

        prediction = Prediction(
            id=str(uuid.uuid4())[:8],
            type=PredictionType.STOCK_PICK.value,
            stock_id=stock_id,
            stock_name=stock_name,
            created_at=now.strftime('%Y-%m-%d %H:%M:%S'),
            created_price=current_price,
            expected_return=expected_return,
            verify_days=verify_days,
            expire_date=expire_date,
            source=source,
            strategy_params=strategy_params,
            notes=notes
        )

        self.predictions.append(prediction)
        self._save_data()
        return prediction

    def add_batch_stock_picks(
        self,
        stocks: List[Dict],
        verify_days: int = 5,
        source: str = None,
        strategy_params: Dict = None
    ) -> List[Prediction]:
        """
        批次新增選股預測

        Parameters:
        -----------
        stocks : List[Dict] - 股票列表，每個元素需包含 stock_id, stock_name, current_price
        verify_days : int - 驗證天數
        source : str - 策略來源
        strategy_params : Dict - 策略參數

        Returns:
        --------
        List[Prediction] - 新增的預測列表
        """
        predictions = []
        for stock in stocks:
            p = self.add_stock_pick_prediction(
                stock_id=stock['stock_id'],
                stock_name=stock['stock_name'],
                current_price=stock['current_price'],
                expected_return=stock.get('expected_return'),
                verify_days=verify_days,
                source=source,
                strategy_params=strategy_params
            )
            predictions.append(p)
        return predictions

    def verify_predictions(self, price_data: pd.DataFrame) -> Dict:
        """
        驗證所有待驗證的預測

        Parameters:
        -----------
        price_data : pd.DataFrame - 股價資料（收盤價），index 為日期，columns 為股票代號

        Returns:
        --------
        Dict - 驗證結果摘要
        """
        today = datetime.now().date()
        results = {
            'verified_count': 0,
            'success_count': 0,
            'failed_count': 0,
            'expired_count': 0,
            'details': []
        }

        for prediction in self.predictions:
            if prediction.status != PredictionStatus.PENDING.value:
                continue

            stock_id = prediction.stock_id
            if stock_id not in price_data.columns:
                continue

            # 取得預測後的股價資料
            created_date = datetime.strptime(prediction.created_at, '%Y-%m-%d %H:%M:%S').date()
            expire_date = datetime.strptime(prediction.expire_date, '%Y-%m-%d').date()

            # 篩選預測期間的股價
            mask = (price_data.index.date > created_date) & (price_data.index.date <= today)
            period_prices = price_data.loc[mask, stock_id].dropna()

            if len(period_prices) == 0:
                continue

            # 記錄期間最高/最低價
            prediction.highest_price = float(period_prices.max())
            prediction.lowest_price = float(period_prices.min())

            # 最新收盤價
            latest_price = float(period_prices.iloc[-1])
            prediction.verified_price = latest_price
            prediction.actual_return = (latest_price - prediction.created_price) / prediction.created_price * 100

            # 根據預測類型驗證
            verified = False

            if prediction.type == PredictionType.TARGET_PRICE.value:
                # 目標價達成：期間內最高價是否達到目標價
                if prediction.target_price:
                    if prediction.target_price > prediction.created_price:
                        # 看多：最高價達到目標價
                        verified = prediction.highest_price >= prediction.target_price
                    else:
                        # 看空：最低價達到目標價
                        verified = prediction.lowest_price <= prediction.target_price

                    if verified:
                        prediction.status = PredictionStatus.SUCCESS.value
                        results['success_count'] += 1
                    elif today >= expire_date:
                        prediction.status = PredictionStatus.FAILED.value
                        results['failed_count'] += 1

            elif prediction.type == PredictionType.DIRECTION.value:
                # 漲跌方向：驗證日的收盤價與預測方向是否一致
                if today >= expire_date:
                    if prediction.predicted_direction == 'up':
                        verified = latest_price > prediction.created_price
                    else:
                        verified = latest_price < prediction.created_price

                    prediction.status = PredictionStatus.SUCCESS.value if verified else PredictionStatus.FAILED.value
                    if verified:
                        results['success_count'] += 1
                    else:
                        results['failed_count'] += 1

            elif prediction.type == PredictionType.STOCK_PICK.value:
                # 選股勝率：驗證日收盤價是否高於買入價
                if today >= expire_date:
                    verified = latest_price > prediction.created_price
                    prediction.status = PredictionStatus.SUCCESS.value if verified else PredictionStatus.FAILED.value
                    if verified:
                        results['success_count'] += 1
                    else:
                        results['failed_count'] += 1

            # 記錄驗證時間
            if prediction.status != PredictionStatus.PENDING.value:
                prediction.verified_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                results['verified_count'] += 1
                results['details'].append({
                    'id': prediction.id,
                    'stock': f"{prediction.stock_id} {prediction.stock_name}",
                    'type': prediction.type,
                    'status': prediction.status,
                    'return': prediction.actual_return
                })

        # 處理過期的預測
        for prediction in self.predictions:
            if prediction.status == PredictionStatus.PENDING.value:
                expire_date = datetime.strptime(prediction.expire_date, '%Y-%m-%d').date()
                if today > expire_date + timedelta(days=3):  # 給 3 天緩衝
                    prediction.status = PredictionStatus.EXPIRED.value
                    prediction.verified_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    results['expired_count'] += 1

        self._save_data()

        # 記錄驗證日誌
        if results['verified_count'] > 0:
            self.verification_log.append({
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'results': results
            })
            self._save_data()

        return results

    def get_statistics(self, days: int = 30, prediction_type: str = None) -> Dict:
        """
        取得預測統計

        Parameters:
        -----------
        days : int - 統計最近幾天的資料
        prediction_type : str - 篩選特定預測類型

        Returns:
        --------
        Dict - 統計結果
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # 篩選預測
        filtered = [
            p for p in self.predictions
            if datetime.strptime(p.created_at, '%Y-%m-%d %H:%M:%S') >= cutoff_date
            and (prediction_type is None or p.type == prediction_type)
        ]

        total = len(filtered)
        if total == 0:
            return {
                'total': 0,
                'pending': 0,
                'success': 0,
                'failed': 0,
                'expired': 0,
                'success_rate': 0,
                'avg_return': 0,
                'by_type': {},
                'by_source': {}
            }

        # 計算各狀態數量
        pending = sum(1 for p in filtered if p.status == PredictionStatus.PENDING.value)
        success = sum(1 for p in filtered if p.status == PredictionStatus.SUCCESS.value)
        failed = sum(1 for p in filtered if p.status == PredictionStatus.FAILED.value)
        expired = sum(1 for p in filtered if p.status == PredictionStatus.EXPIRED.value)

        # 計算勝率（僅計算已驗證的）
        verified = success + failed
        success_rate = (success / verified * 100) if verified > 0 else 0

        # 計算平均報酬
        returns = [p.actual_return for p in filtered if p.actual_return is not None]
        avg_return = sum(returns) / len(returns) if returns else 0

        # 依類型統計
        by_type = {}
        for ptype in PredictionType:
            type_filtered = [p for p in filtered if p.type == ptype.value]
            type_verified = [p for p in type_filtered if p.status in [PredictionStatus.SUCCESS.value, PredictionStatus.FAILED.value]]
            type_success = sum(1 for p in type_filtered if p.status == PredictionStatus.SUCCESS.value)

            by_type[ptype.value] = {
                'total': len(type_filtered),
                'verified': len(type_verified),
                'success': type_success,
                'success_rate': (type_success / len(type_verified) * 100) if type_verified else 0
            }

        # 依來源統計
        by_source = {}
        sources = set(p.source for p in filtered if p.source)
        for source in sources:
            source_filtered = [p for p in filtered if p.source == source]
            source_verified = [p for p in source_filtered if p.status in [PredictionStatus.SUCCESS.value, PredictionStatus.FAILED.value]]
            source_success = sum(1 for p in source_filtered if p.status == PredictionStatus.SUCCESS.value)
            source_returns = [p.actual_return for p in source_filtered if p.actual_return is not None]

            by_source[source] = {
                'total': len(source_filtered),
                'verified': len(source_verified),
                'success': source_success,
                'success_rate': (source_success / len(source_verified) * 100) if source_verified else 0,
                'avg_return': sum(source_returns) / len(source_returns) if source_returns else 0
            }

        return {
            'total': total,
            'pending': pending,
            'success': success,
            'failed': failed,
            'expired': expired,
            'success_rate': success_rate,
            'avg_return': avg_return,
            'by_type': by_type,
            'by_source': by_source
        }

    def get_pending_predictions(self) -> List[Prediction]:
        """取得所有待驗證的預測"""
        return [p for p in self.predictions if p.status == PredictionStatus.PENDING.value]

    def get_recent_predictions(self, days: int = 7, status: str = None) -> List[Prediction]:
        """取得最近的預測記錄"""
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered = [
            p for p in self.predictions
            if datetime.strptime(p.created_at, '%Y-%m-%d %H:%M:%S') >= cutoff_date
        ]

        if status:
            filtered = [p for p in filtered if p.status == status]

        # 按建立時間排序（最新在前）
        filtered.sort(key=lambda x: x.created_at, reverse=True)
        return filtered

    def cancel_prediction(self, prediction_id: str) -> bool:
        """取消預測"""
        for p in self.predictions:
            if p.id == prediction_id and p.status == PredictionStatus.PENDING.value:
                p.status = PredictionStatus.CANCELLED.value
                p.verified_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self._save_data()
                return True
        return False

    def to_dataframe(self, days: int = 30) -> pd.DataFrame:
        """轉換為 DataFrame 方便分析"""
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered = [
            p for p in self.predictions
            if datetime.strptime(p.created_at, '%Y-%m-%d %H:%M:%S') >= cutoff_date
        ]

        if not filtered:
            return pd.DataFrame()

        return pd.DataFrame([asdict(p) for p in filtered])


# 全域實例
_tracker = None

def get_tracker() -> PredictionTracker:
    """取得預測追蹤器實例"""
    global _tracker
    if _tracker is None:
        _tracker = PredictionTracker()
    return _tracker
