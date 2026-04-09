"""
成長投資策略
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from .base import BaseStrategy


class GrowthStrategy(BaseStrategy):
    """
    成長投資策略

    篩選條件:
    - 營收年增率 (YoY)
    - 營收月增率 (MoM)
    - 連續營收成長
    """

    name = "成長投資"
    description = "篩選營收高成長的股票"

    def get_default_params(self) -> Dict[str, Any]:
        return {
            'revenue_yoy_min': 20.0,    # 營收年增率下限 (%)
            'revenue_mom_min': 10.0,    # 營收月增率下限 (%)
            'consecutive_months': 3,     # 連續成長月數
            'use_yoy': True,
            'use_mom': True,
            'use_consecutive': True,
        }

    def get_param_info(self) -> Dict[str, Dict[str, Any]]:
        return {
            'revenue_yoy_min': {
                'type': 'float',
                'min': -50.0,
                'max': 200.0,
                'default': 20.0,
                'description': '營收年增率下限 (%)',
                'step': 5.0,
            },
            'revenue_mom_min': {
                'type': 'float',
                'min': -50.0,
                'max': 100.0,
                'default': 10.0,
                'description': '營收月增率下限 (%)',
                'step': 5.0,
            },
            'consecutive_months': {
                'type': 'int',
                'min': 1,
                'max': 12,
                'default': 3,
                'description': '連續成長月數',
                'step': 1,
            },
        }

    def filter(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> List[str]:
        """篩選符合成長投資條件的股票"""
        conditions = []

        # 營收年增率條件
        if self.params['use_yoy'] and 'revenue_yoy' in data:
            yoy = data['revenue_yoy']
            if date is None:
                date = yoy.index.max()

            if date in yoy.index:
                yoy_latest = yoy.loc[date]
                yoy_cond = yoy_latest >= self.params['revenue_yoy_min']
                conditions.append(yoy_cond)

        # 營收月增率條件
        if self.params['use_mom'] and 'revenue_mom' in data:
            mom = data['revenue_mom']
            if date is None:
                date = mom.index.max()

            if date in mom.index:
                mom_latest = mom.loc[date]
                mom_cond = mom_latest >= self.params['revenue_mom_min']
                conditions.append(mom_cond)

        # 連續成長條件
        if self.params['use_consecutive'] and 'revenue_yoy' in data:
            yoy = data['revenue_yoy']
            n_months = self.params['consecutive_months']

            if date is None:
                date = yoy.index.max()

            # 取最近 N 個月的數據
            date_idx = yoy.index.get_loc(date) if date in yoy.index else -1
            if date_idx >= n_months - 1:
                recent_data = yoy.iloc[date_idx - n_months + 1:date_idx + 1]
                # 檢查每個月都是正成長
                consecutive_cond = (recent_data > 0).all()
                conditions.append(consecutive_cond)

        # 合併所有條件
        if not conditions:
            return []

        combined = conditions[0]
        for cond in conditions[1:]:
            combined, cond = combined.align(cond, fill_value=False)
            combined = combined & cond

        combined = combined.fillna(False)

        result = []
        for idx in combined[combined].index:
            idx_str = str(idx)
            stock_id = idx_str.split(' ')[0] if ' ' in idx_str else idx_str
            result.append(stock_id)
        return result

    def score(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> pd.Series:
        """
        計算成長評分

        評分方式: 營收成長率的加權平均
        """
        scores = pd.Series(dtype=float)
        score_components = []

        # 營收年增率評分
        if self.params['use_yoy'] and 'revenue_yoy' in data:
            yoy = data['revenue_yoy']
            if date is None:
                date = yoy.index.max()

            if date in yoy.index:
                yoy_latest = yoy.loc[date]
                # 轉換為百分位排名
                yoy_score = yoy_latest.rank(pct=True) * 100
                score_components.append(yoy_score)

        # 營收月增率評分
        if self.params['use_mom'] and 'revenue_mom' in data:
            mom = data['revenue_mom']
            if date is None:
                date = mom.index.max()

            if date in mom.index:
                mom_latest = mom.loc[date]
                mom_score = mom_latest.rank(pct=True) * 100
                score_components.append(mom_score)

        # 計算連續成長月數作為額外分數
        if self.params['use_consecutive'] and 'revenue_yoy' in data:
            yoy = data['revenue_yoy']
            if date is None:
                date = yoy.index.max()

            # 計算連續正成長月數
            consecutive_months = self._calc_consecutive_growth(yoy, date)
            consecutive_score = (consecutive_months / 12) * 100  # 最多12個月
            score_components.append(consecutive_score)

        if score_components:
            combined = pd.concat(score_components, axis=1)
            scores = combined.mean(axis=1)

        return scores

    def _calc_consecutive_growth(self, data: pd.DataFrame, date: pd.Timestamp) -> pd.Series:
        """計算到指定日期為止的連續正成長月數（向量化實作）"""
        if date not in data.index:
            return pd.Series(0, index=data.columns)

        date_idx = data.index.get_loc(date)
        # 取到指定日期為止的所有資料（含當日），由舊到新
        subset = data.iloc[:date_idx + 1]

        is_growth = (subset > 0).astype(int)  # shape: (T, n_stocks)

        # 從最後一列往前，找到每欄第一個 0 的位置，其後的 1 才算連續
        # 技巧：對 is_growth 做 reversed cumsum，再找連續尾段
        # 等效：從末尾往前累計，遇到 0 中斷
        reversed_growth = is_growth.iloc[::-1]
        # cummin 沿列方向：一旦遇到 0，後續（往前方向）都變 0
        consecutive_mask = reversed_growth.cumprod()
        return consecutive_mask.sum(axis=0)
