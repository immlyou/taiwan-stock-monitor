"""
回測引擎模組
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import sys
from pathlib import Path

from config import TRADING_COSTS, BACKTEST_DEFAULTS, PRICE_LIMITS
from core.backtest.metrics import calculate_metrics, compare_with_benchmark, PerformanceMetrics


@dataclass
class Trade:
    """單筆交易記錄"""
    stock_id: str
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    shares: int = 0
    pnl: float = 0.0
    return_pct: float = 0.0
    holding_days: int = 0


@dataclass
class BacktestResult:
    """回測結果"""
    portfolio_values: pd.Series          # 淨值序列
    trades: pd.DataFrame                  # 交易記錄
    positions: pd.DataFrame               # 持倉記錄
    metrics: PerformanceMetrics          # 績效指標
    benchmark_comparison: Dict[str, Any] = field(default_factory=dict)  # 與大盤比較
    config: Dict[str, Any] = field(default_factory=dict)  # 回測設定


class BacktestEngine:
    """
    回測引擎

    支援:
    - 定期換股 (月/季)
    - 交易成本計算
    - 資金管理 (等權重/市值加權)
    """

    def __init__(self,
                 initial_capital: float = None,
                 commission_rate: float = None,
                 tax_rate: float = None,
                 commission_discount: float = None):
        """
        初始化回測引擎

        Parameters:
        -----------
        initial_capital : float
            初始資金
        commission_rate : float
            手續費率
        tax_rate : float
            交易稅率
        commission_discount : float
            手續費折扣
        """
        self.initial_capital = initial_capital if initial_capital is not None else BACKTEST_DEFAULTS['initial_capital']
        self.commission_rate = commission_rate if commission_rate is not None else TRADING_COSTS['commission_rate']
        self.tax_rate = tax_rate if tax_rate is not None else TRADING_COSTS['tax_rate']
        self.commission_discount = commission_discount if commission_discount is not None else TRADING_COSTS['discount']

        # 漲跌幅限制設定
        self.price_limit_enabled = PRICE_LIMITS.get('enabled', True)
        self.up_limit = PRICE_LIMITS.get('up_limit', 0.10)
        self.down_limit = PRICE_LIMITS.get('down_limit', -0.10)

        # 回測狀態
        self.cash = self.initial_capital
        self.positions: Dict[str, Dict] = {}  # stock_id -> {shares, cost}
        self.trades: List[Trade] = []
        self.portfolio_history: List[Dict] = []

    # 最低手續費常數
    MIN_COMMISSION = 20  # 台股最低手續費 20 元

    def _check_price_limit(self, stock_id: str, current_price: float,
                           prev_close: pd.Series) -> tuple:
        """
        檢查股票是否觸及漲跌停

        Parameters:
        -----------
        stock_id : str
            股票代號
        current_price : float
            當日價格
        prev_close : pd.Series
            前一日收盤價 Series

        Returns:
        --------
        tuple of (can_buy: bool, can_sell: bool, adjusted_price: float)
            - can_buy: 是否可以買入 (漲停時無法買入)
            - can_sell: 是否可以賣出 (跌停時無法賣出)
            - adjusted_price: 調整後的價格
        """
        if not self.price_limit_enabled:
            return True, True, current_price

        if stock_id not in prev_close.index or pd.isna(prev_close[stock_id]):
            return True, True, current_price

        prev_price = prev_close[stock_id]
        if prev_price <= 0:
            return True, True, current_price

        change_pct = (current_price - prev_price) / prev_price

        # 漲停：股價漲幅 >= 10%，無法買入（買不到）
        if change_pct >= self.up_limit:
            return False, True, prev_price * (1 + self.up_limit)

        # 跌停：股價跌幅 <= -10%，無法賣出（賣不掉）
        if change_pct <= self.down_limit:
            return True, False, prev_price * (1 + self.down_limit)

        return True, True, current_price

    def _calculate_transaction_cost(self, amount: float, is_sell: bool = False) -> float:
        """
        計算交易成本

        Parameters:
        -----------
        amount : float
            交易金額
        is_sell : bool
            是否為賣出交易

        Returns:
        --------
        float
            總交易成本（手續費 + 交易稅）

        Notes:
        ------
        - 手續費有最低 20 元限制
        - 交易稅只在賣出時收取
        """
        # 計算手續費，取最低手續費與計算手續費的較大值
        calculated_commission = amount * self.commission_rate * self.commission_discount
        commission = max(calculated_commission, self.MIN_COMMISSION) if amount > 0 else 0

        # 交易稅只在賣出時收取
        tax = amount * self.tax_rate if is_sell else 0

        return commission + tax

    # pandas 2.2+ 頻率別名相容對照表（舊 -> 新）
    _FREQ_COMPAT = {'M': 'ME', 'Q': 'QE', '2Q': '2QE', 'Y': 'YE'}

    def _get_rebalance_dates(self, start_date: pd.Timestamp,
                             end_date: pd.Timestamp,
                             freq: str = 'M') -> List[pd.Timestamp]:
        """取得換股日期列表"""
        freq = self._FREQ_COMPAT.get(freq, freq)
        dates = pd.date_range(start=start_date, end=end_date, freq=freq)
        return dates.tolist()

    def _allocate_weights(self, stocks: List[str],
                          market_values: Optional[pd.Series] = None,
                          method: str = 'equal') -> Dict[str, float]:
        """
        分配權重

        Parameters:
        -----------
        stocks : list
            股票列表
        market_values : pd.Series, optional
            市值數據
        method : str
            分配方法: 'equal' 或 'market_cap'

        Returns:
        --------
        dict
            股票代號 -> 權重
        """
        if not stocks:
            return {}

        if method == 'market_cap' and market_values is not None:
            # 市值加權
            mv = market_values.reindex(stocks).dropna()
            total_mv = mv.sum()
            if total_mv > 0:
                weights = (mv / total_mv).to_dict()
            else:
                weights = {s: 1.0 / len(stocks) for s in stocks}
        else:
            # 等權重
            weights = {s: 1.0 / len(stocks) for s in stocks}

        return weights

    def _rebalance(self, date: pd.Timestamp,
                   target_stocks: List[str],
                   prices: pd.Series,
                   weights: Dict[str, float],
                   prev_prices: Optional[pd.Series] = None):
        """
        執行換股

        Parameters:
        -----------
        date : pd.Timestamp
            換股日期
        target_stocks : list
            目標持股
        prices : pd.Series
            當日股價
        weights : dict
            目標權重
        prev_prices : pd.Series, optional
            前一日收盤價，用於漲跌停判斷
        """
        # 計算當前投資組合總價值
        portfolio_value = self.cash
        for stock_id, pos in self.positions.items():
            if stock_id in prices.index and not pd.isna(prices[stock_id]):
                portfolio_value += pos['shares'] * prices[stock_id]

        # 賣出不在目標清單中的股票
        stocks_to_sell = [s for s in self.positions.keys() if s not in target_stocks]
        for stock_id in stocks_to_sell:
            if stock_id in prices.index and not pd.isna(prices[stock_id]):
                # 漲跌停檢查：跌停時無法賣出
                can_buy, can_sell, adjusted_price = self._check_price_limit(
                    stock_id, prices[stock_id], prev_prices if prev_prices is not None else pd.Series(dtype=float)
                )
                if can_sell:
                    self._sell(stock_id, date, adjusted_price)

        # 計算目標金額
        target_amounts = {s: portfolio_value * weights.get(s, 0) for s in target_stocks}

        # 調整現有持倉並買入新股票
        for stock_id in target_stocks:
            if stock_id not in prices.index or pd.isna(prices[stock_id]):
                continue

            price = prices[stock_id]

            # 漲跌停檢查：漲停時無法買入
            can_buy, can_sell, adjusted_price = self._check_price_limit(
                stock_id, price, prev_prices if prev_prices is not None else pd.Series(dtype=float)
            )

            target_amount = target_amounts[stock_id]
            current_amount = 0

            if stock_id in self.positions:
                current_amount = self.positions[stock_id]['shares'] * adjusted_price

            diff = target_amount - current_amount

            if diff > 0 and can_buy:
                # 需要買入
                self._buy(stock_id, date, adjusted_price, diff)
            elif diff < -adjusted_price and can_sell:  # 只有差額大於一股才賣
                # 需要賣出
                shares_to_sell = int(abs(diff) / adjusted_price)
                if shares_to_sell > 0:
                    self._partial_sell(stock_id, date, adjusted_price, shares_to_sell)

    def _buy(self, stock_id: str, date: pd.Timestamp, price: float, amount: float):
        """買入股票"""
        if amount <= 0 or self.cash <= 0:
            return

        # 計算可買股數 (取整數)
        shares = int(amount / price)
        if shares <= 0:
            return

        cost = shares * price
        transaction_cost = self._calculate_transaction_cost(cost, is_sell=False)
        total_cost = cost + transaction_cost

        if total_cost > self.cash:
            # 資金不足，用精確公式重新計算可買股數
            max_amount = self.cash / (1 + self.commission_rate * self.commission_discount)
            shares = int(max_amount / price)
            if shares <= 0:
                return
            cost = shares * price
            transaction_cost = self._calculate_transaction_cost(cost, is_sell=False)
            total_cost = cost + transaction_cost
            # 最終安全檢查：確保不會超出現金
            if total_cost > self.cash:
                return

        # 更新現金
        self.cash -= total_cost

        # 更新持倉
        if stock_id in self.positions:
            old_shares = self.positions[stock_id]['shares']
            old_cost = self.positions[stock_id]['cost']
            self.positions[stock_id] = {
                'shares': old_shares + shares,
                'cost': old_cost + cost,
                'entry_date': self.positions[stock_id]['entry_date'],
            }
        else:
            self.positions[stock_id] = {
                'shares': shares,
                'cost': cost,
                'entry_date': date,
            }

    def _sell(self, stock_id: str, date: pd.Timestamp, price: float):
        """賣出全部股票"""
        if stock_id not in self.positions:
            return

        pos = self.positions[stock_id]
        shares = pos['shares']
        proceeds = shares * price
        transaction_cost = self._calculate_transaction_cost(proceeds, is_sell=True)

        # 計算損益
        cost = pos['cost']
        pnl = proceeds - cost - transaction_cost
        return_pct = (pnl / cost) * 100 if cost > 0 else 0

        # 記錄交易
        trade = Trade(
            stock_id=stock_id,
            entry_date=pos['entry_date'],
            entry_price=cost / shares if shares > 0 else 0,
            exit_date=date,
            exit_price=price,
            shares=shares,
            pnl=pnl,
            return_pct=return_pct,
            holding_days=(date - pos['entry_date']).days,
        )
        self.trades.append(trade)

        # 更新現金和持倉
        self.cash += proceeds - transaction_cost
        del self.positions[stock_id]

    def _partial_sell(self, stock_id: str, date: pd.Timestamp, price: float, shares: int):
        """部分賣出"""
        if stock_id not in self.positions:
            return

        pos = self.positions[stock_id]
        if shares >= pos['shares']:
            self._sell(stock_id, date, price)
            return

        proceeds = shares * price
        transaction_cost = self._calculate_transaction_cost(proceeds, is_sell=True)

        # 計算部分成本
        cost_per_share = pos['cost'] / pos['shares']
        partial_cost = cost_per_share * shares

        # 更新持倉
        self.positions[stock_id]['shares'] -= shares
        self.positions[stock_id]['cost'] -= partial_cost

        # 更新現金
        self.cash += proceeds - transaction_cost

    def _record_portfolio_value(self, date: pd.Timestamp, prices: pd.Series):
        """記錄投資組合價值"""
        portfolio_value = self.cash

        for stock_id, pos in self.positions.items():
            if stock_id in prices.index and not pd.isna(prices[stock_id]):
                portfolio_value += pos['shares'] * prices[stock_id]

        self.portfolio_history.append({
            'date': date,
            'value': portfolio_value,
            'cash': self.cash,
            'positions': len(self.positions),
        })

    def run(self,
            strategy_func: Callable,
            data: Dict[str, pd.DataFrame],
            start_date: Optional[pd.Timestamp] = None,
            end_date: Optional[pd.Timestamp] = None,
            rebalance_freq: str = 'M',
            max_stocks: int = 10,
            weight_method: str = 'equal',
            benchmark: Optional[pd.Series] = None) -> BacktestResult:
        """
        執行回測

        Parameters:
        -----------
        strategy_func : callable
            策略函數，接收 (data, date) 回傳股票列表
        data : dict
            數據字典
        start_date : pd.Timestamp
            開始日期
        end_date : pd.Timestamp
            結束日期
        rebalance_freq : str
            換股頻率 ('M'=月, 'Q'=季)
        max_stocks : int
            最大持股數
        weight_method : str
            權重方法 ('equal', 'market_cap')
        benchmark : pd.Series
            大盤指數數據

        Returns:
        --------
        BacktestResult
            回測結果
        """
        # 重置狀態
        self.cash = self.initial_capital
        self.positions = {}
        self.trades = []
        self.portfolio_history = []

        # 取得價格數據
        close = data.get('close')
        if close is None:
            raise ValueError("數據中缺少 'close' 價格數據")

        market_values = data.get('market_value')

        # 設定日期範圍
        if start_date is None:
            start_date = close.index.min()
        if end_date is None:
            end_date = close.index.max()

        # 取得換股日期
        rebalance_dates = self._get_rebalance_dates(start_date, end_date, rebalance_freq)

        # 取得所有交易日
        trading_dates = close.index[(close.index >= start_date) & (close.index <= end_date)]

        # 執行回測
        next_rebalance_idx = 0
        prev_prices = None

        for date in trading_dates:
            prices = close.loc[date]

            # 檢查是否需要換股
            if (next_rebalance_idx < len(rebalance_dates) and
                date >= rebalance_dates[next_rebalance_idx]):

                # 執行策略取得目標股票
                target_stocks = strategy_func(data, date)

                # 限制股票數量
                if len(target_stocks) > max_stocks:
                    target_stocks = target_stocks[:max_stocks]

                # 計算權重
                mv = market_values.loc[date] if market_values is not None and date in market_values.index else None
                weights = self._allocate_weights(target_stocks, mv, weight_method)

                # 執行換股 (傳入前一日價格做漲跌停判斷)
                self._rebalance(date, target_stocks, prices, weights, prev_prices)

                next_rebalance_idx += 1

            # 記錄當日投資組合價值
            self._record_portfolio_value(date, prices)
            prev_prices = prices

        # 將回測結束時仍持有的部位轉為 exit_date=None 的 Trade 記錄
        last_date = trading_dates[-1] if len(trading_dates) > 0 else end_date
        for stock_id, pos in list(self.positions.items()):
            shares = pos['shares']
            cost = pos['cost']
            trade = Trade(
                stock_id=stock_id,
                entry_date=pos['entry_date'],
                entry_price=cost / shares if shares > 0 else 0,
                exit_date=None,
                exit_price=None,
                shares=shares,
                pnl=0.0,
                return_pct=0.0,
                holding_days=(last_date - pos['entry_date']).days,
            )
            self.trades.append(trade)

        # 整理結果
        if not self.portfolio_history:
            raise ValueError("回測期間無交易日資料，請確認日期範圍")

        portfolio_df = pd.DataFrame(self.portfolio_history)
        portfolio_values = portfolio_df.set_index('date')['value']

        trades_df = pd.DataFrame([
            {
                'stock_id': t.stock_id,
                'entry_date': t.entry_date,
                'entry_price': t.entry_price,
                'exit_date': t.exit_date,
                'exit_price': t.exit_price,
                'shares': t.shares,
                'pnl': t.pnl,
                'return': t.return_pct,
                'holding_days': t.holding_days,
            }
            for t in self.trades
        ])

        # 計算績效指標
        metrics = calculate_metrics(portfolio_values, trades_df)

        # 與大盤比較
        benchmark_comparison = {}
        if benchmark is not None:
            benchmark_comparison = compare_with_benchmark(portfolio_values, benchmark)

        return BacktestResult(
            portfolio_values=portfolio_values,
            trades=trades_df,
            positions=portfolio_df,
            metrics=metrics,
            benchmark_comparison=benchmark_comparison,
            config={
                'initial_capital': self.initial_capital,
                'start_date': start_date,
                'end_date': end_date,
                'rebalance_freq': rebalance_freq,
                'max_stocks': max_stocks,
                'weight_method': weight_method,
            }
        )


def quick_backtest(strategy,
                   data: Dict[str, pd.DataFrame],
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   **kwargs) -> BacktestResult:
    """
    快速回測函數

    Parameters:
    -----------
    strategy : BaseStrategy
        策略實例
    data : dict
        數據字典
    start_date : str
        開始日期 (YYYY-MM-DD)
    end_date : str
        結束日期 (YYYY-MM-DD)
    **kwargs
        其他回測參數

    Returns:
    --------
    BacktestResult
        回測結果
    """
    engine = BacktestEngine()

    # 轉換日期
    if start_date:
        start_date = pd.Timestamp(start_date)
    if end_date:
        end_date = pd.Timestamp(end_date)

    # 策略函數包裝
    def strategy_func(data, date):
        return strategy.filter(data, date)

    # 取得大盤數據
    benchmark = data.get('benchmark')
    if benchmark is not None and isinstance(benchmark, pd.DataFrame):
        benchmark = benchmark.iloc[:, 0]

    return engine.run(
        strategy_func=strategy_func,
        data=data,
        start_date=start_date,
        end_date=end_date,
        benchmark=benchmark,
        **kwargs
    )
