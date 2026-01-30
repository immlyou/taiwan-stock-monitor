"""
策略基礎類別
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd
from dataclasses import dataclass, field


@dataclass
class StrategyResult:
    """策略執行結果"""
    stocks: List[str]                    # 符合條件的股票列表
    scores: Optional[pd.Series] = None   # 各股票評分
    details: Dict[str, Any] = field(default_factory=dict)  # 詳細資訊
    date: Optional[pd.Timestamp] = None  # 執行日期


class BaseStrategy(ABC):
    """
    策略基礎類別 - 所有選股策略都應繼承此類別

    Attributes:
    -----------
    name : str
        策略名稱
    description : str
        策略描述
    params : dict
        策略參數
    """

    name: str = "基礎策略"
    description: str = "策略描述"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        初始化策略

        Parameters:
        -----------
        params : dict, optional
            策略參數，會覆蓋預設參數
        """
        self.params = self.get_default_params()
        if params:
            self.params.update(params)

    @abstractmethod
    def get_default_params(self) -> Dict[str, Any]:
        """
        取得預設參數

        Returns:
        --------
        dict
            預設參數字典
        """
        pass

    @abstractmethod
    def filter(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> List[str]:
        """
        篩選符合條件的股票

        Parameters:
        -----------
        data : dict
            數據字典，包含各種數據 DataFrame
        date : pd.Timestamp, optional
            篩選日期，預設為最新日期

        Returns:
        --------
        List[str]
            符合條件的股票代號列表
        """
        pass

    def score(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> pd.Series:
        """
        計算各股票評分 (可選實作)

        Parameters:
        -----------
        data : dict
            數據字典
        date : pd.Timestamp, optional
            計算日期

        Returns:
        --------
        pd.Series
            各股票評分，index 為股票代號
        """
        # 預設實作：符合條件的股票得 1 分，其他 0 分
        stocks = self.filter(data, date)
        all_stocks = data.get('close', pd.DataFrame()).columns.tolist()
        scores = pd.Series(0, index=all_stocks)
        scores[stocks] = 1
        return scores

    def run(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> StrategyResult:
        """
        執行策略

        Parameters:
        -----------
        data : dict
            數據字典
        date : pd.Timestamp, optional
            執行日期

        Returns:
        --------
        StrategyResult
            策略執行結果
        """
        stocks = self.filter(data, date)
        scores = self.score(data, date)

        # 建立 index 映射以優化搜索效能 (O(n) 而非 O(n²))
        # 處理 "1101 台泥" vs "1101" 的格式差異
        index_map = {}
        for idx in scores.index:
            idx_str = str(idx)
            # 提取股票代號 (空格前的部分)
            stock_id = idx_str.split(' ')[0] if ' ' in idx_str else idx_str
            index_map[stock_id] = idx

        # 使用映射快速查找評分
        stock_scores = pd.Series(dtype=float)
        if len(stocks) > 0:
            for stock_id in stocks:
                if stock_id in index_map:
                    stock_scores[stock_id] = scores[index_map[stock_id]]

        return StrategyResult(
            stocks=stocks,
            scores=stock_scores,
            details={
                'strategy': self.name,
                'params': self.params,
                'total_candidates': len(stocks),
            },
            date=date
        )

    def get_param_info(self) -> Dict[str, Dict[str, Any]]:
        """
        取得參數資訊 (用於 UI 顯示)

        Returns:
        --------
        dict
            參數名稱 -> {type, min, max, default, description}
        """
        return {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', params={self.params})"


class CombinedStrategy(BaseStrategy):
    """
    組合策略 - 結合多個策略
    """

    name = "組合策略"
    description = "結合多個策略的篩選結果"

    def __init__(self, strategies: List[BaseStrategy], mode: str = 'intersection'):
        """
        Parameters:
        -----------
        strategies : list
            策略列表
        mode : str
            組合模式: 'intersection' (交集) 或 'union' (聯集)
        """
        self.strategies = strategies
        self.mode = mode
        super().__init__()

    def get_default_params(self) -> Dict[str, Any]:
        return {'mode': self.mode}

    def filter(self, data: Dict[str, pd.DataFrame], date: Optional[pd.Timestamp] = None) -> List[str]:
        if not self.strategies:
            return []

        results = [set(s.filter(data, date)) for s in self.strategies]

        if self.mode == 'intersection':
            combined = results[0]
            for r in results[1:]:
                combined = combined & r
        else:  # union
            combined = set()
            for r in results:
                combined = combined | r

        return list(combined)
