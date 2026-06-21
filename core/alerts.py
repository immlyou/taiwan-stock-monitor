"""
警報引擎 - 檢查警報條件並發送通知
"""
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass


from core.indicators import calculate_rsi, calculate_sma
from core.json_store import file_lock
from core.timeutils import now_taipei


@dataclass
class AlertResult:
    """警報檢查結果"""
    alert_id: str
    stock_id: str
    alert_type: str
    is_triggered: bool
    current_value: float
    target_value: float
    message: str


class AlertEngine:
    """
    警報引擎

    支援警報類型:
    - price_above: 價格突破上方
    - price_below: 價格跌破下方
    - rsi_above: RSI 超買
    - rsi_below: RSI 超賣
    - volume_spike: 成交量爆量
    - ma_cross_up: 均線黃金交叉
    - ma_cross_down: 均線死亡交叉
    - new_high: 創新高
    - new_low: 創新低
    """

    ALERTS_FILE = Path(__file__).parent.parent / 'data' / 'alerts.json'

    def __init__(self):
        self.alerts_data = self._load_alerts()

    def _load_alerts(self) -> Dict:
        """載入警報設定"""
        if self.ALERTS_FILE.exists():
            with open(self.ALERTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'alerts': []}

    def _save_alerts(self) -> None:
        """儲存警報設定（使用 atomic write 避免並發寫入損毀）"""
        self.ALERTS_FILE.parent.mkdir(exist_ok=True)
        tmp_path = self.ALERTS_FILE.with_suffix('.tmp')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(self.alerts_data, f, ensure_ascii=False, indent=2, default=str)
        tmp_path.replace(self.ALERTS_FILE)  # atomic rename

    def check_alert(self, alert: Dict, data: Dict[str, pd.DataFrame]) -> AlertResult:
        """
        檢查單個警報

        Parameters:
        -----------
        alert : dict
            警報設定
        data : dict
            數據字典 (close, high, low, volume)

        Returns:
        --------
        AlertResult
            警報檢查結果
        """
        stock_id = alert['stock_id']
        alert_type = alert['type']
        target_value = alert['value']

        close = data.get('close')
        volume = data.get('volume')
        high = data.get('high')
        low = data.get('low')

        if close is None or stock_id not in close.columns:
            return AlertResult(
                alert_id=alert['id'],
                stock_id=stock_id,
                alert_type=alert_type,
                is_triggered=False,
                current_value=0,
                target_value=target_value,
                message='找不到股票數據'
            )

        stock_close = close[stock_id].dropna()
        current_price = stock_close.iloc[-1]
        is_triggered = False
        current_value = current_price
        message = ''

        # 根據警報類型檢查條件
        if alert_type == 'price_above':
            is_triggered = current_price > target_value
            message = f'股價 {current_price:.2f} 已突破 {target_value}'

        elif alert_type == 'price_below':
            is_triggered = current_price < target_value
            message = f'股價 {current_price:.2f} 已跌破 {target_value}'

        elif alert_type == 'rsi_above':
            rsi = calculate_rsi(stock_close, period=14)
            current_value = rsi.iloc[-1]
            is_triggered = current_value > target_value
            message = f'RSI {current_value:.1f} 已超過 {target_value}'

        elif alert_type == 'rsi_below':
            rsi = calculate_rsi(stock_close, period=14)
            current_value = rsi.iloc[-1]
            is_triggered = current_value < target_value
            message = f'RSI {current_value:.1f} 已低於 {target_value}'

        elif alert_type == 'volume_spike':
            if volume is not None and stock_id in volume.columns:
                stock_volume = volume[stock_id].dropna()
                avg_volume = stock_volume.tail(20).mean()
                current_value = stock_volume.iloc[-1]
                volume_ratio = current_value / avg_volume if avg_volume > 0 else 0

                is_triggered = volume_ratio > target_value
                message = f'成交量 {current_value:,.0f} 為均量的 {volume_ratio:.1f} 倍'

        elif alert_type == 'ma_cross_up':
            # 解析短期和長期均線參數
            if isinstance(target_value, str) and ',' in target_value:
                short_period, long_period = map(int, target_value.split(','))
            else:
                short_period, long_period = 5, 20

            short_ma = calculate_sma(stock_close, short_period)
            long_ma = calculate_sma(stock_close, long_period)

            # 檢查黃金交叉 (需要至少 2 個資料點)
            if len(short_ma) >= 2 and len(long_ma) >= 2:
                prev_short = short_ma.iloc[-2]
                prev_long = long_ma.iloc[-2]
                curr_short = short_ma.iloc[-1]
                curr_long = long_ma.iloc[-1]

                is_triggered = (prev_short <= prev_long) and (curr_short > curr_long)
                current_value = curr_short
                message = f'MA{short_period}={curr_short:.2f} 向上穿越 MA{long_period}={curr_long:.2f}'

        elif alert_type == 'ma_cross_down':
            if isinstance(target_value, str) and ',' in target_value:
                short_period, long_period = map(int, target_value.split(','))
            else:
                short_period, long_period = 5, 20

            short_ma = calculate_sma(stock_close, short_period)
            long_ma = calculate_sma(stock_close, long_period)

            # 需要至少 2 個資料點
            if len(short_ma) >= 2 and len(long_ma) >= 2:
                prev_short = short_ma.iloc[-2]
                prev_long = long_ma.iloc[-2]
                curr_short = short_ma.iloc[-1]
                curr_long = long_ma.iloc[-1]

                is_triggered = (prev_short >= prev_long) and (curr_short < curr_long)
                current_value = curr_short
                message = f'MA{short_period}={curr_short:.2f} 向下穿越 MA{long_period}={curr_long:.2f}'

        elif alert_type == 'new_high':
            lookback = int(target_value)
            # 比較當前價格與「之前」N日的最高價 (排除今日)
            if len(stock_close) > lookback:
                prev_highest = stock_close.iloc[-(lookback+1):-1].max()
                is_triggered = current_price > prev_highest
            else:
                is_triggered = False
            current_value = current_price
            message = f'股價 {current_price:.2f} 創 {lookback} 日新高'

        elif alert_type == 'new_low':
            lookback = int(target_value)
            # 比較當前價格與「之前」N日的最低價 (排除今日)
            if len(stock_close) > lookback:
                prev_lowest = stock_close.iloc[-(lookback+1):-1].min()
                is_triggered = current_price < prev_lowest
            else:
                is_triggered = False
            current_value = current_price
            message = f'股價 {current_price:.2f} 創 {lookback} 日新低'

        return AlertResult(
            alert_id=alert['id'],
            stock_id=stock_id,
            alert_type=alert_type,
            is_triggered=bool(is_triggered),   # 確保是 Python bool，而非 np.bool_
            current_value=float(current_value) if not isinstance(current_value, str) else current_value,
            target_value=target_value if not isinstance(target_value, str) else 0,
            message=message
        )

    def check_all_alerts(self, data: Dict[str, pd.DataFrame]) -> List[AlertResult]:
        """
        檢查所有啟用中的警報

        Parameters:
        -----------
        data : dict
            數據字典

        Returns:
        --------
        list of AlertResult
            觸發的警報結果
        """
        triggered_results = []
        triggered_ids = []

        for alert in self.alerts_data.get('alerts', []):
            # 跳過已停用或已觸發的警報
            if not alert.get('enabled') or alert.get('triggered'):
                continue

            result = self.check_alert(alert, data)

            if result.is_triggered:
                # 更新警報狀態（觸發時間用台北時區）
                alert['triggered'] = True
                alert['triggered_at'] = now_taipei().isoformat()
                triggered_results.append(result)
                triggered_ids.append(alert.get('id'))

        # 儲存更新後的警報狀態。在鎖內重新載入並只回寫 triggered 標記，
        # 避免用本實例的舊快照整檔覆蓋掉其他請求併發做的修改。
        if triggered_results:
            with file_lock(self.ALERTS_FILE):
                fresh = self._load_alerts()
                now_iso = now_taipei().isoformat()
                for alert in fresh.get('alerts', []):
                    if alert.get('id') in triggered_ids and not alert.get('triggered'):
                        alert['triggered'] = True
                        alert['triggered_at'] = now_iso
                self.alerts_data = fresh
                self._save_alerts()

        return triggered_results

    def get_active_alerts(self) -> List[Dict]:
        """取得所有啟用中的警報"""
        return [
            a for a in self.alerts_data.get('alerts', [])
            if a.get('enabled') and not a.get('triggered')
        ]

    def get_triggered_alerts(self) -> List[Dict]:
        """取得所有已觸發的警報"""
        return [
            a for a in self.alerts_data.get('alerts', [])
            if a.get('triggered')
        ]

    def reset_alert(self, alert_id: str) -> bool:
        """重設警報（清除觸發狀態）"""
        for alert in self.alerts_data.get('alerts', []):
            if alert['id'] == alert_id:
                alert['triggered'] = False
                alert['triggered_at'] = None
                self._save_alerts()
                return True
        return False

    def disable_alert(self, alert_id: str) -> bool:
        """停用警報"""
        for alert in self.alerts_data.get('alerts', []):
            if alert['id'] == alert_id:
                alert['enabled'] = False
                self._save_alerts()
                return True
        return False

    def enable_alert(self, alert_id: str) -> bool:
        """啟用警報"""
        for alert in self.alerts_data.get('alerts', []):
            if alert['id'] == alert_id:
                alert['enabled'] = True
                self._save_alerts()
                return True
        return False


def check_alerts_and_notify(data: Dict[str, pd.DataFrame],
                            send_notification: bool = True,
                            cooldown_sec: int | None = None) -> List[AlertResult]:
    """
    檢查警報並發送通知

    Parameters:
    -----------
    data : dict
        數據字典
    send_notification : bool
        是否發送通知
    cooldown_sec : int, optional
        每條警報的通知冷卻秒數。自動排程開啟後，盤中會反覆檢查；
        透過節流避免同一警報重複轟炸。None 時讀 env
        ALERT_NOTIFY_COOLDOWN_SEC（預設 3600 秒）。

    Returns:
    --------
    list of AlertResult
        觸發的警報
    """
    engine = AlertEngine()
    triggered = engine.check_all_alerts(data)

    if triggered and send_notification:
        try:
            import os
            from core.notification import send_notification as notify, get_throttle

            if cooldown_sec is None:
                cooldown_sec = int(os.getenv('ALERT_NOTIFY_COOLDOWN_SEC', '3600'))
            throttle = get_throttle()

            # 逐條套用節流：冷卻期內已通知過的警報不再列入本次訊息。
            messages = []
            for result in triggered:
                if throttle.allow(f'alert:{result.alert_id}', cooldown_sec):
                    messages.append(f"🔔 {result.stock_id}: {result.message}")

            if messages:
                notify(
                    title='台股警報通知',
                    message='\n'.join(messages)
                )
        except Exception as e:
            print(f'發送通知失敗: {e}')

    return triggered
