"""
價值投資策略
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from .base import BaseStrategy


def _extract_stock_id(column_name: str) -> str:
    """從欄位名稱中提取股票代號"""
    if ' ' in column_name:
        return column_name.split(' ')[0]
    return column_name


class ValueStrategy(BaseStrategy):
    """
    價值投資策略

    篩選條件:
    - 低本益比 (PE)
    - 低股價淨值比 (PB)
    - 高殖利率
    """

    name = "價值投資"
    description = "篩選低估值、高殖利率的股票"

    def get_default_params(self) -> Dict[str, Any]:
        return {
            'pe_max': 15.0,           # 本益比上限
            'pb_max': 1.5,            # 股價淨值比上限
            'dividend_yield_min': 4.0, # 殖利率下限 (%)
            'use_pe': True,
            'use_pb': True,
            'use_dividend': True,
        }

    def get_param_info(self) -> Dict[str, Dict[str, Any]]:
        return {
            'pe_max': {
                'type': 'float',
                'min': 1.0,
                'max': 50.0,
                'default': 15.0,
                'description': '本益比上限',
                'step': 0.5,
            },
            'pb_max': {
                'type': 'float',
                'min': 0.1,
                'max': 5.0,
                'default': 1.5,
                'description': '股價淨值比上限',
                'step': 0.1,
            },
            'dividend_yield_min': {
                'type': 'float',
                'min': 0.0,
                'max': 15.0,
                'default': 4.0,
                'description': '殖利率下限 (%)',
                'step': 0.5,
            },
        }

    def filter(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> List[str]:
        """篩選符合價值投資條件的股票"""
        conditions = []

        # 取得最新日期的數據
        if date is None:
            date = data.get('pe_ratio', pd.DataFrame()).index.max()

        # 本益比條件
        if self.params['use_pe'] and 'pe_ratio' in data:
            pe = data['pe_ratio']
            if date in pe.index:
                pe_latest = pe.loc[date]
                pe_cond = (pe_latest > 0) & (pe_latest <= self.params['pe_max'])
                conditions.append(pe_cond)

        # 股價淨值比條件
        if self.params['use_pb'] and 'pb_ratio' in data:
            pb = data['pb_ratio']
            if date in pb.index:
                pb_latest = pb.loc[date]
                pb_cond = (pb_latest > 0) & (pb_latest <= self.params['pb_max'])
                conditions.append(pb_cond)

        # 殖利率條件
        if self.params['use_dividend'] and 'dividend_yield' in data:
            dy = data['dividend_yield']
            if date in dy.index:
                dy_latest = dy.loc[date]
                dy_cond = dy_latest >= self.params['dividend_yield_min']
                conditions.append(dy_cond)

        # 合併所有條件
        if not conditions:
            return []

        combined = conditions[0]
        for cond in conditions[1:]:
            # 對齊 index
            combined, cond = combined.align(cond, fill_value=False)
            combined = combined & cond

        # 過濾 NaN
        combined = combined.fillna(False)

        # 提取股票代號 (處理 "1101 台泥" 這種格式)
        result = []
        for idx in combined[combined].index:
            stock_id = _extract_stock_id(str(idx))
            result.append(stock_id)

        return result

    def score(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> pd.Series:
        """
        計算價值評分

        評分方式: 各指標排名百分位的加權平均
        - 本益比: 越低分數越高
        - 股價淨值比: 越低分數越高
        - 殖利率: 越高分數越高
        """
        scores = pd.Series(dtype=float)

        if date is None:
            date = data.get('pe_ratio', pd.DataFrame()).index.max()

        score_components = []

        # 本益比評分 (越低越好)
        if self.params['use_pe'] and 'pe_ratio' in data:
            pe = data['pe_ratio']
            if date in pe.index:
                pe_latest = pe.loc[date]
                # 只考慮正值
                pe_valid = pe_latest[pe_latest > 0]
                pe_score = 100 - pe_valid.rank(pct=True) * 100
                score_components.append(pe_score)

        # 股價淨值比評分 (越低越好)
        if self.params['use_pb'] and 'pb_ratio' in data:
            pb = data['pb_ratio']
            if date in pb.index:
                pb_latest = pb.loc[date]
                pb_valid = pb_latest[pb_latest > 0]
                pb_score = 100 - pb_valid.rank(pct=True) * 100
                score_components.append(pb_score)

        # 殖利率評分 (越高越好)
        if self.params['use_dividend'] and 'dividend_yield' in data:
            dy = data['dividend_yield']
            if date in dy.index:
                dy_latest = dy.loc[date]
                dy_valid = dy_latest[dy_latest >= 0]
                dy_score = dy_valid.rank(pct=True) * 100
                score_components.append(dy_score)

        # 計算平均分數
        if score_components:
            # 對齊所有分數
            combined = pd.concat(score_components, axis=1)
            scores = combined.mean(axis=1)

        return scores
