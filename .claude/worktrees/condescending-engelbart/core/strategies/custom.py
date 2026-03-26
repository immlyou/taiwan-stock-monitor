"""
自訂多因子篩選策略

允許使用者動態組合多個篩選條件，支援 AND/OR 組合模式。
"""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import pandas as pd
import numpy as np

from .base import BaseStrategy, StrategyResult


# 可選欄位（中文名 -> data_key）
AVAILABLE_FIELDS = {
    '本益比': {'key': 'pe_ratio', 'unit': '倍', 'default_op': '<=', 'default_val': 15.0},
    '股價淨值比': {'key': 'pb_ratio', 'unit': '倍', 'default_op': '<=', 'default_val': 1.5},
    '殖利率(%)': {'key': 'dividend_yield', 'unit': '%', 'default_op': '>=', 'default_val': 4.0},
    '營收年增率(%)': {'key': 'revenue_yoy', 'unit': '%', 'default_op': '>=', 'default_val': 10.0},
    '營收月增率(%)': {'key': 'revenue_mom', 'unit': '%', 'default_op': '>=', 'default_val': 5.0},
    '收盤價': {'key': 'close', 'unit': '元', 'default_op': '>=', 'default_val': 10.0},
    '成交量(張)': {'key': 'volume', 'unit': '張', 'default_op': '>=', 'default_val': 500.0},
}

OPERATORS = {
    '>=': lambda s, v: s >= v,
    '<=': lambda s, v: s <= v,
    '>': lambda s, v: s > v,
    '<': lambda s, v: s < v,
    '==': lambda s, v: s == v,
}


@dataclass
class FilterCondition:
    """單一篩選條件"""
    field_name: str   # 中文欄位名
    operator: str     # 運算子
    value: float      # 門檻值
    enabled: bool = True

    def to_dict(self):
        return {
            'field_name': self.field_name,
            'operator': self.operator,
            'value': self.value,
            'enabled': self.enabled,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class CustomStrategy(BaseStrategy):
    """自訂多因子篩選策略"""

    name = "自訂篩選"
    description = "自訂條件組合篩選"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params)
        self.conditions: List[FilterCondition] = []
        if params and 'conditions' in params:
            self.conditions = [
                FilterCondition.from_dict(c) if isinstance(c, dict) else c
                for c in params['conditions']
            ]
        self.combine_mode = params.get('combine_mode', 'AND') if params else 'AND'

    def get_default_params(self) -> Dict[str, Any]:
        return {
            'conditions': [],
            'combine_mode': 'AND',
        }

    def _get_latest_values(self, data: Dict[str, pd.DataFrame], data_key: str) -> pd.Series:
        """取得某個指標的最新值 (所有股票)"""
        df = data.get(data_key)
        if df is None or df.empty:
            return pd.Series(dtype=float)
        # 成交量需要除以 1000 轉換成張
        result = df.iloc[-1].dropna()
        if data_key == 'volume':
            result = result / 1000
        return result

    def filter(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> List[str]:
        active_conditions = [c for c in self.conditions if c.enabled]

        if not active_conditions:
            return []

        # 取得所有可用股票
        close = data.get('close')
        if close is None or close.empty:
            return []
        all_stocks = set(close.columns)

        results_per_condition = []

        for cond in active_conditions:
            field_info = AVAILABLE_FIELDS.get(cond.field_name)
            if not field_info:
                continue

            values = self._get_latest_values(data, field_info['key'])
            if values.empty:
                results_per_condition.append(set())
                continue

            op_fn = OPERATORS.get(cond.operator)
            if op_fn is None:
                continue

            mask = op_fn(values, cond.value)
            passing = set(mask[mask].index) & all_stocks
            results_per_condition.append(passing)

        if not results_per_condition:
            return []

        if self.combine_mode == 'AND':
            combined = results_per_condition[0]
            for s in results_per_condition[1:]:
                combined = combined & s
        else:  # OR
            combined = set()
            for s in results_per_condition:
                combined = combined | s

        return sorted(combined)

    def score(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> pd.Series:
        """計算評分：通過越多條件分數越高"""
        active_conditions = [c for c in self.conditions if c.enabled]
        if not active_conditions:
            return pd.Series(dtype=float)

        close = data.get('close')
        if close is None or close.empty:
            return pd.Series(dtype=float)

        all_stocks = close.columns.tolist()
        scores = pd.Series(0.0, index=all_stocks)

        for cond in active_conditions:
            field_info = AVAILABLE_FIELDS.get(cond.field_name)
            if not field_info:
                continue

            values = self._get_latest_values(data, field_info['key'])
            if values.empty:
                continue

            op_fn = OPERATORS.get(cond.operator)
            if op_fn is None:
                continue

            mask = op_fn(values, cond.value)
            passing_stocks = mask[mask].index
            for s in passing_stocks:
                if s in scores.index:
                    scores[s] += 1.0

        # 正規化到 0-100
        max_score = len(active_conditions)
        if max_score > 0:
            scores = (scores / max_score * 100).round(1)

        return scores


# ========== 儲存/載入 ==========
CUSTOM_STRATEGIES_DIR = Path(__file__).parent.parent.parent / 'data'


def save_custom_strategy(name: str, conditions: List[FilterCondition], combine_mode: str = 'AND'):
    """儲存自訂策略"""
    CUSTOM_STRATEGIES_DIR.mkdir(exist_ok=True)
    filepath = CUSTOM_STRATEGIES_DIR / 'custom_strategies.json'

    strategies = load_all_custom_strategies()
    strategies[name] = {
        'conditions': [c.to_dict() for c in conditions],
        'combine_mode': combine_mode,
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(strategies, f, ensure_ascii=False, indent=2)


def load_all_custom_strategies() -> Dict[str, Any]:
    """載入所有自訂策略"""
    filepath = CUSTOM_STRATEGIES_DIR / 'custom_strategies.json'
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def delete_custom_strategy(name: str):
    """刪除自訂策略"""
    strategies = load_all_custom_strategies()
    if name in strategies:
        del strategies[name]
        filepath = CUSTOM_STRATEGIES_DIR / 'custom_strategies.json'
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(strategies, f, ensure_ascii=False, indent=2)
