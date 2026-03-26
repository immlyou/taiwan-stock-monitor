"""
動能投資策略
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from .base import BaseStrategy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from indicators import rsi, sma, volume_ratio, breakout_signal


class MomentumStrategy(BaseStrategy):
    """
    動能投資策略

    篩選條件:
    - 價格突破 N 日高點
    - 成交量放大
    - RSI 在強勢區間
    """

    name = "動能投資"
    description = "篩選價格與成交量動能強勁的股票"

    def get_default_params(self) -> Dict[str, Any]:
        return {
            'breakout_days': 20,       # 突破天數
            'volume_ratio_min': 1.5,   # 量比下限
            'volume_ma_days': 5,       # 量比計算天數
            'rsi_min': 50,             # RSI 下限
            'rsi_max': 80,             # RSI 上限
            'rsi_period': 14,          # RSI 週期
            'use_breakout': True,
            'use_volume': True,
            'use_rsi': True,
        }

    def get_param_info(self) -> Dict[str, Dict[str, Any]]:
        return {
            'breakout_days': {
                'type': 'int',
                'min': 5,
                'max': 120,
                'default': 20,
                'description': '突破天數',
                'step': 5,
            },
            'volume_ratio_min': {
                'type': 'float',
                'min': 0.5,
                'max': 5.0,
                'default': 1.5,
                'description': '量比下限',
                'step': 0.1,
            },
            'rsi_min': {
                'type': 'int',
                'min': 0,
                'max': 100,
                'default': 50,
                'description': 'RSI 下限',
                'step': 5,
            },
            'rsi_max': {
                'type': 'int',
                'min': 0,
                'max': 100,
                'default': 80,
                'description': 'RSI 上限',
                'step': 5,
            },
        }

    def filter(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> List[str]:
        """篩選符合動能投資條件的股票"""
        conditions = []

        close = data.get('close')
        volume = data.get('volume')

        if close is None:
            return []

        if date is None:
            date = close.index.max()

        # 價格突破條件
        if self.params['use_breakout']:
            breakout = breakout_signal(close, self.params['breakout_days'])
            if date in breakout.index:
                breakout_cond = breakout.loc[date]
                conditions.append(breakout_cond)

        # 成交量條件
        if self.params['use_volume'] and volume is not None:
            vol_ratio = volume_ratio(volume, self.params['volume_ma_days'])
            if date in vol_ratio.index:
                vol_cond = vol_ratio.loc[date] >= self.params['volume_ratio_min']
                conditions.append(vol_cond)

        # RSI 條件
        if self.params['use_rsi']:
            rsi_values = rsi(close, self.params['rsi_period'])
            if date in rsi_values.index:
                rsi_latest = rsi_values.loc[date]
                rsi_cond = (rsi_latest >= self.params['rsi_min']) & (rsi_latest <= self.params['rsi_max'])
                conditions.append(rsi_cond)

        # 合併所有條件
        if not conditions:
            return []

        combined = conditions[0]
        for cond in conditions[1:]:
            combined, cond = combined.align(cond, fill_value=False)
            combined = combined & cond

        combined = combined.fillna(False)

        return combined[combined].index.tolist()

    def score(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> pd.Series:
        """
        計算動能評分

        評分方式: 各動能指標的加權平均
        """
        scores = pd.Series(dtype=float)
        score_components = []

        close = data.get('close')
        volume = data.get('volume')

        if close is None:
            return scores

        if date is None:
            date = close.index.max()

        # 價格動能評分 (相對於N日高點的位置)
        if self.params['use_breakout']:
            high_n = close.rolling(window=self.params['breakout_days'], min_periods=1).max()
            if date in close.index:
                price_strength = close.loc[date] / high_n.loc[date]
                price_score = price_strength.rank(pct=True) * 100
                score_components.append(price_score)

        # 成交量動能評分
        if self.params['use_volume'] and volume is not None:
            vol_ratio_values = volume_ratio(volume, self.params['volume_ma_days'])
            if date in vol_ratio_values.index:
                vol_score = vol_ratio_values.loc[date].rank(pct=True) * 100
                score_components.append(vol_score)

        # RSI 評分
        if self.params['use_rsi']:
            rsi_values = rsi(close, self.params['rsi_period'])
            if date in rsi_values.index:
                # RSI 在 50-80 區間越高越好
                rsi_latest = rsi_values.loc[date]
                rsi_score = rsi_latest.rank(pct=True) * 100
                score_components.append(rsi_score)

        if score_components:
            combined = pd.concat(score_components, axis=1)
            scores = combined.mean(axis=1)

        return scores
