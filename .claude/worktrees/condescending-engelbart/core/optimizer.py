"""
策略參數優化器模組 - Grid Search 與交叉驗證
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Callable, Optional, Tuple
from dataclasses import dataclass
from itertools import product
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.logging_config import get_logger

logger = get_logger('optimizer')


@dataclass
class OptimizationResult:
    """優化結果"""
    best_params: Dict[str, Any]           # 最佳參數組合
    best_score: float                      # 最佳分數
    all_results: pd.DataFrame              # 所有結果
    metric_used: str                       # 使用的評估指標
    total_combinations: int                # 總組合數
    elapsed_time: float                    # 執行時間


class GridSearchOptimizer:
    """
    Grid Search 參數優化器

    透過窮舉搜索找出最佳參數組合
    """

    def __init__(self,
                 strategy_class,
                 param_grid: Dict[str, List],
                 metric: str = 'sharpe_ratio',
                 higher_is_better: bool = True):
        """
        Parameters:
        -----------
        strategy_class : class
            策略類別
        param_grid : dict
            參數網格，例如:
            {
                'pe_max': [10, 12, 15, 20],
                'pb_max': [1.0, 1.5, 2.0],
                'dividend_yield_min': [3.0, 4.0, 5.0],
            }
        metric : str
            評估指標名稱
        higher_is_better : bool
            分數越高越好 (True) 或越低越好 (False)
        """
        self.strategy_class = strategy_class
        self.param_grid = param_grid
        self.metric = metric
        self.higher_is_better = higher_is_better

    def _generate_combinations(self) -> List[Dict[str, Any]]:
        """產生所有參數組合"""
        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())

        combinations = []
        for combo in product(*values):
            params = dict(zip(keys, combo))
            combinations.append(params)

        return combinations

    def _evaluate_params(self, params: Dict[str, Any],
                         data: Dict[str, pd.DataFrame],
                         backtest_func: Callable) -> float:
        """
        評估單一參數組合

        Parameters:
        -----------
        params : dict
            參數組合
        data : dict
            數據字典
        backtest_func : callable
            回測函數，接收 (strategy, data) 回傳回測結果

        Returns:
        --------
        float
            評估分數
        """
        try:
            strategy = self.strategy_class(params)
            result = backtest_func(strategy, data)

            # 從回測結果中取得指標
            if hasattr(result, 'metrics'):
                metrics = result.metrics
                if hasattr(metrics, self.metric):
                    return getattr(metrics, self.metric)
                elif isinstance(metrics, dict) and self.metric in metrics:
                    return metrics[self.metric]

            return float('-inf') if self.higher_is_better else float('inf')

        except Exception as e:
            logger.warning(f'參數組合 {params} 評估失敗: {e}')
            return float('-inf') if self.higher_is_better else float('inf')

    def optimize(self, data: Dict[str, pd.DataFrame],
                 backtest_func: Callable,
                 verbose: bool = True) -> OptimizationResult:
        """
        執行優化

        Parameters:
        -----------
        data : dict
            數據字典
        backtest_func : callable
            回測函數
        verbose : bool
            是否顯示進度

        Returns:
        --------
        OptimizationResult
            優化結果
        """
        import time
        start_time = time.time()

        combinations = self._generate_combinations()
        total = len(combinations)

        if verbose:
            logger.info(f'開始 Grid Search: {total} 種參數組合')

        results = []

        for i, params in enumerate(combinations):
            score = self._evaluate_params(params, data, backtest_func)

            results.append({
                **params,
                'score': score,
            })

            if verbose and (i + 1) % max(1, total // 10) == 0:
                logger.info(f'進度: {i + 1}/{total} ({(i + 1) / total * 100:.1f}%)')

        # 轉換為 DataFrame
        results_df = pd.DataFrame(results)

        # 找出最佳結果
        if self.higher_is_better:
            best_idx = results_df['score'].idxmax()
        else:
            best_idx = results_df['score'].idxmin()

        best_row = results_df.loc[best_idx]
        best_params = {k: v for k, v in best_row.items() if k != 'score'}
        best_score = best_row['score']

        elapsed_time = time.time() - start_time

        if verbose:
            logger.info(f'優化完成，耗時 {elapsed_time:.2f} 秒')
            logger.info(f'最佳參數: {best_params}')
            logger.info(f'最佳 {self.metric}: {best_score:.4f}')

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            all_results=results_df,
            metric_used=self.metric,
            total_combinations=total,
            elapsed_time=elapsed_time,
        )


class WalkForwardOptimizer:
    """
    Walk-Forward 優化器

    使用滾動窗口進行樣本外測試，避免過擬合
    """

    def __init__(self,
                 strategy_class,
                 param_grid: Dict[str, List],
                 in_sample_months: int = 12,
                 out_sample_months: int = 3,
                 metric: str = 'sharpe_ratio'):
        """
        Parameters:
        -----------
        strategy_class : class
            策略類別
        param_grid : dict
            參數網格
        in_sample_months : int
            樣本內期間（月數）
        out_sample_months : int
            樣本外期間（月數）
        metric : str
            評估指標
        """
        self.strategy_class = strategy_class
        self.param_grid = param_grid
        self.in_sample_months = in_sample_months
        self.out_sample_months = out_sample_months
        self.metric = metric

    def _split_periods(self, start_date: pd.Timestamp,
                       end_date: pd.Timestamp) -> List[Tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
        """
        分割時間區間

        Returns:
        --------
        list
            [(in_sample_start, in_sample_end, out_sample_start, out_sample_end), ...]
        """
        from dateutil.relativedelta import relativedelta

        periods = []
        current_start = start_date

        while True:
            in_sample_end = current_start + relativedelta(months=self.in_sample_months) - pd.Timedelta(days=1)
            out_sample_start = in_sample_end + pd.Timedelta(days=1)
            out_sample_end = out_sample_start + relativedelta(months=self.out_sample_months) - pd.Timedelta(days=1)

            if out_sample_end > end_date:
                break

            periods.append((current_start, in_sample_end, out_sample_start, out_sample_end))

            # 滾動窗口
            current_start = out_sample_start

        return periods

    def optimize(self, data: Dict[str, pd.DataFrame],
                 backtest_func: Callable,
                 start_date: Optional[pd.Timestamp] = None,
                 end_date: Optional[pd.Timestamp] = None) -> Dict[str, Any]:
        """
        執行 Walk-Forward 優化

        Parameters:
        -----------
        data : dict
            數據字典
        backtest_func : callable
            回測函數
        start_date : pd.Timestamp, optional
            開始日期
        end_date : pd.Timestamp, optional
            結束日期

        Returns:
        --------
        dict
            優化結果
        """
        # 取得日期範圍
        close = data.get('close')
        if close is None:
            raise ValueError("數據中缺少 'close'")

        if start_date is None:
            start_date = close.index.min()
        if end_date is None:
            end_date = close.index.max()

        periods = self._split_periods(start_date, end_date)

        if not periods:
            raise ValueError('日期範圍不足以進行 Walk-Forward 分析')

        logger.info(f'Walk-Forward 分析: {len(periods)} 個窗口')

        results = []

        for i, (is_start, is_end, os_start, os_end) in enumerate(periods):
            logger.info(f'窗口 {i + 1}: 樣本內 {is_start.date()} ~ {is_end.date()}, '
                       f'樣本外 {os_start.date()} ~ {os_end.date()}')

            # 樣本內優化
            grid_search = GridSearchOptimizer(
                self.strategy_class,
                self.param_grid,
                self.metric,
            )

            # 創建樣本內數據子集
            in_sample_data = {}
            for key, df in data.items():
                if isinstance(df, pd.DataFrame) and isinstance(df.index, pd.DatetimeIndex):
                    mask = (df.index >= is_start) & (df.index <= is_end)
                    in_sample_data[key] = df[mask]
                else:
                    in_sample_data[key] = df

            opt_result = grid_search.optimize(in_sample_data, backtest_func, verbose=False)

            # 樣本外測試
            out_sample_data = {}
            for key, df in data.items():
                if isinstance(df, pd.DataFrame) and isinstance(df.index, pd.DatetimeIndex):
                    mask = (df.index >= os_start) & (df.index <= os_end)
                    out_sample_data[key] = df[mask]
                else:
                    out_sample_data[key] = df

            strategy = self.strategy_class(opt_result.best_params)
            try:
                os_result = backtest_func(strategy, out_sample_data)
                os_score = getattr(os_result.metrics, self.metric, 0)
            except Exception:
                os_score = 0

            results.append({
                'period': i + 1,
                'in_sample_start': is_start,
                'in_sample_end': is_end,
                'out_sample_start': os_start,
                'out_sample_end': os_end,
                'best_params': opt_result.best_params,
                'in_sample_score': opt_result.best_score,
                'out_sample_score': os_score,
            })

        results_df = pd.DataFrame(results)

        # 計算統計
        avg_in_sample = results_df['in_sample_score'].mean()
        avg_out_sample = results_df['out_sample_score'].mean()
        efficiency = avg_out_sample / avg_in_sample if avg_in_sample != 0 else 0

        return {
            'results': results_df,
            'avg_in_sample_score': avg_in_sample,
            'avg_out_sample_score': avg_out_sample,
            'efficiency_ratio': efficiency,
            'total_periods': len(periods),
        }


def quick_optimize(strategy_class,
                   param_grid: Dict[str, List],
                   data: Dict[str, pd.DataFrame],
                   metric: str = 'sharpe_ratio') -> OptimizationResult:
    """
    快速優化便利函數

    Parameters:
    -----------
    strategy_class : class
        策略類別
    param_grid : dict
        參數網格
    data : dict
        數據字典
    metric : str
        評估指標

    Returns:
    --------
    OptimizationResult
        優化結果
    """
    from core.backtest.engine import quick_backtest

    def backtest_func(strategy, data):
        return quick_backtest(strategy, data)

    optimizer = GridSearchOptimizer(strategy_class, param_grid, metric)
    return optimizer.optimize(data, backtest_func)
