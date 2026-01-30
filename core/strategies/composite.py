"""
綜合策略 - 結合多種因子的選股策略
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from .base import BaseStrategy
from .value import ValueStrategy
from .growth import GrowthStrategy
from .momentum import MomentumStrategy


class CompositeStrategy(BaseStrategy):
    """
    綜合策略

    結合價值、成長、動能三種因子，使用加權評分系統篩選股票
    """

    name = "綜合策略"
    description = "結合價值、成長、動能因子的綜合選股"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params)

        # 初始化子策略
        self.value_strategy = ValueStrategy()
        self.growth_strategy = GrowthStrategy()
        self.momentum_strategy = MomentumStrategy()

    def get_default_params(self) -> Dict[str, Any]:
        return {
            # 權重設定
            'value_weight': 0.4,      # 價值因子權重
            'growth_weight': 0.3,     # 成長因子權重
            'momentum_weight': 0.3,   # 動能因子權重

            # 篩選設定
            'top_n': 20,              # 選取前 N 名
            'min_score': 50,          # 最低分數門檻

            # 是否啟用各因子
            'use_value': True,
            'use_growth': True,
            'use_momentum': True,

            # 子策略參數 (可選覆蓋)
            'value_params': None,
            'growth_params': None,
            'momentum_params': None,
        }

    def get_param_info(self) -> Dict[str, Dict[str, Any]]:
        return {
            'value_weight': {
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.4,
                'description': '價值因子權重',
                'step': 0.1,
            },
            'growth_weight': {
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.3,
                'description': '成長因子權重',
                'step': 0.1,
            },
            'momentum_weight': {
                'type': 'float',
                'min': 0.0,
                'max': 1.0,
                'default': 0.3,
                'description': '動能因子權重',
                'step': 0.1,
            },
            'top_n': {
                'type': 'int',
                'min': 5,
                'max': 50,
                'default': 20,
                'description': '選取前 N 名',
                'step': 5,
            },
            'min_score': {
                'type': 'float',
                'min': 0,
                'max': 100,
                'default': 50,
                'description': '最低分數門檻',
                'step': 5,
            },
        }

    def _update_sub_strategies(self):
        """更新子策略參數"""
        if self.params.get('value_params'):
            self.value_strategy.params.update(self.params['value_params'])
        if self.params.get('growth_params'):
            self.growth_strategy.params.update(self.params['growth_params'])
        if self.params.get('momentum_params'):
            self.momentum_strategy.params.update(self.params['momentum_params'])

    def score(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> pd.Series:
        """
        計算綜合評分

        評分方式: 各因子評分的加權平均
        """
        self._update_sub_strategies()

        score_components = []
        weights = []

        # 價值因子
        if self.params['use_value']:
            value_scores = self.value_strategy.score(data, date)
            if len(value_scores) > 0:
                score_components.append(value_scores)
                weights.append(self.params['value_weight'])

        # 成長因子
        if self.params['use_growth']:
            growth_scores = self.growth_strategy.score(data, date)
            if len(growth_scores) > 0:
                score_components.append(growth_scores)
                weights.append(self.params['growth_weight'])

        # 動能因子
        if self.params['use_momentum']:
            momentum_scores = self.momentum_strategy.score(data, date)
            if len(momentum_scores) > 0:
                score_components.append(momentum_scores)
                weights.append(self.params['momentum_weight'])

        if not score_components:
            return pd.Series(dtype=float)

        # 標準化權重
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]

        # 合併評分
        combined = pd.concat(score_components, axis=1)
        combined.columns = range(len(score_components))

        # 加權平均
        weighted_scores = pd.Series(0.0, index=combined.index)
        for i, w in enumerate(weights):
            weighted_scores += combined[i].fillna(0) * w

        return weighted_scores

    def filter(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> List[str]:
        """
        篩選股票

        根據綜合評分選取前 N 名且分數高於門檻的股票
        """
        scores = self.score(data, date)

        if len(scores) == 0:
            return []

        # 過濾最低分數
        valid_scores = scores[scores >= self.params['min_score']]

        # 排序取前 N 名
        top_stocks = valid_scores.nlargest(self.params['top_n'])

        return top_stocks.index.tolist()

    def get_factor_breakdown(self, data: Dict[str, pd.DataFrame],
                              date: Optional[pd.Timestamp] = None) -> pd.DataFrame:
        """
        取得各因子評分明細

        Returns:
        --------
        pd.DataFrame
            包含各因子評分的 DataFrame
        """
        self._update_sub_strategies()

        breakdown = pd.DataFrame()

        if self.params['use_value']:
            breakdown['價值因子'] = self.value_strategy.score(data, date)

        if self.params['use_growth']:
            breakdown['成長因子'] = self.growth_strategy.score(data, date)

        if self.params['use_momentum']:
            breakdown['動能因子'] = self.momentum_strategy.score(data, date)

        breakdown['綜合評分'] = self.score(data, date)

        return breakdown
