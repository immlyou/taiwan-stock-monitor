# -*- coding: utf-8 -*-
"""
資金流向分析模組

追蹤三大法人買賣超、連續買賣超天數、產業資金流向
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class InstitutionalFlow:
    """法人買賣超資料"""
    stock_id: str
    name: str
    category: str
    foreign_net: float      # 外資買賣超 (張)
    investment_trust_net: float  # 投信買賣超 (張)
    dealer_net: float       # 自營商買賣超 (張)
    total_net: float        # 三大法人合計
    foreign_holding_pct: float  # 外資持股比例
    consecutive_days: int   # 連續買超天數 (負數為連續賣超)


def calculate_institutional_flow(
    foreign_df: pd.DataFrame,
    investment_trust_df: pd.DataFrame,
    dealer_df: pd.DataFrame,
    stock_info: pd.DataFrame,
    foreign_holding_df: pd.DataFrame = None,
) -> Dict[str, InstitutionalFlow]:
    """
    計算法人買賣超資料

    Parameters:
    -----------
    foreign_df : pd.DataFrame
        外資買賣超資料
    investment_trust_df : pd.DataFrame
        投信買賣超資料
    dealer_df : pd.DataFrame
        自營商買賣超資料
    stock_info : pd.DataFrame
        股票基本資料
    foreign_holding_df : pd.DataFrame
        外資持股比例資料

    Returns:
    --------
    Dict[str, InstitutionalFlow]
        股票代號 -> 法人買賣超資料
    """
    results = {}

    # 取得最新一天的資料
    if foreign_df is None or len(foreign_df) == 0:
        return results

    latest_date = foreign_df.index[-1]
    foreign_latest = foreign_df.iloc[-1]
    investment_trust_latest = investment_trust_df.iloc[-1] if investment_trust_df is not None else pd.Series()
    dealer_latest = dealer_df.iloc[-1] if dealer_df is not None else pd.Series()

    # 計算連續買賣超天數
    consecutive_days = calculate_consecutive_days(foreign_df)

    # 外資持股比例
    foreign_holding_latest = foreign_holding_df.iloc[-1] if foreign_holding_df is not None and len(foreign_holding_df) > 0 else pd.Series()

    # 建立股票資訊對照表
    stock_info_dict = {}
    if stock_info is not None:
        for _, row in stock_info.iterrows():
            stock_info_dict[row['stock_id']] = {
                'name': row.get('name', ''),
                'category': row.get('category', '其他'),
            }

    # 處理每支股票
    for stock_id in foreign_latest.index:
        foreign_net = foreign_latest.get(stock_id, 0)
        if pd.isna(foreign_net):
            foreign_net = 0

        investment_trust_net = investment_trust_latest.get(stock_id, 0)
        if pd.isna(investment_trust_net):
            investment_trust_net = 0

        dealer_net = dealer_latest.get(stock_id, 0)
        if pd.isna(dealer_net):
            dealer_net = 0

        # 單位轉換 (股 -> 張)
        foreign_net = foreign_net / 1000
        investment_trust_net = investment_trust_net / 1000
        dealer_net = dealer_net / 1000

        total_net = foreign_net + investment_trust_net + dealer_net

        # 股票資訊
        info = stock_info_dict.get(stock_id, {'name': '', 'category': '其他'})

        # 外資持股比例
        holding_pct = foreign_holding_latest.get(stock_id, 0)
        if pd.isna(holding_pct):
            holding_pct = 0

        # 連續天數
        cons_days = consecutive_days.get(stock_id, 0)

        results[stock_id] = InstitutionalFlow(
            stock_id=stock_id,
            name=info['name'],
            category=info['category'],
            foreign_net=foreign_net,
            investment_trust_net=investment_trust_net,
            dealer_net=dealer_net,
            total_net=total_net,
            foreign_holding_pct=holding_pct,
            consecutive_days=cons_days,
        )

    return results


def calculate_consecutive_days(df: pd.DataFrame, days: int = 30) -> Dict[str, int]:
    """
    計算連續買賣超天數

    Parameters:
    -----------
    df : pd.DataFrame
        買賣超資料 (日期為 index, 股票代號為 columns)
    days : int
        回溯天數

    Returns:
    --------
    Dict[str, int]
        股票代號 -> 連續天數 (正數為買超，負數為賣超)
    """
    results = {}

    if df is None or len(df) == 0:
        return results

    # 取最近 N 天
    recent_df = df.tail(days)

    for stock_id in recent_df.columns:
        values = recent_df[stock_id].dropna().values

        if len(values) == 0:
            results[stock_id] = 0
            continue

        # 從最後一天開始往前計算連續天數
        latest_sign = 1 if values[-1] > 0 else (-1 if values[-1] < 0 else 0)

        if latest_sign == 0:
            results[stock_id] = 0
            continue

        count = 0
        for val in reversed(values):
            current_sign = 1 if val > 0 else (-1 if val < 0 else 0)
            if current_sign == latest_sign:
                count += 1
            else:
                break

        results[stock_id] = count * latest_sign

    return results


def get_top_flows(
    flows: Dict[str, InstitutionalFlow],
    flow_type: str = 'foreign',
    top_n: int = 20,
    ascending: bool = False,
) -> List[InstitutionalFlow]:
    """
    取得買賣超排行

    Parameters:
    -----------
    flows : Dict[str, InstitutionalFlow]
        法人買賣超資料
    flow_type : str
        'foreign' (外資), 'investment_trust' (投信), 'dealer' (自營商), 'total' (合計)
    top_n : int
        取前 N 名
    ascending : bool
        是否升序 (True 為賣超排行)

    Returns:
    --------
    List[InstitutionalFlow]
        排行榜
    """
    flow_list = list(flows.values())

    if flow_type == 'foreign':
        flow_list.sort(key=lambda x: x.foreign_net, reverse=not ascending)
    elif flow_type == 'investment_trust':
        flow_list.sort(key=lambda x: x.investment_trust_net, reverse=not ascending)
    elif flow_type == 'dealer':
        flow_list.sort(key=lambda x: x.dealer_net, reverse=not ascending)
    else:  # total
        flow_list.sort(key=lambda x: x.total_net, reverse=not ascending)

    return flow_list[:top_n]


def get_sector_flow(
    flows: Dict[str, InstitutionalFlow],
) -> pd.DataFrame:
    """
    計算產業資金流向

    Parameters:
    -----------
    flows : Dict[str, InstitutionalFlow]
        法人買賣超資料

    Returns:
    --------
    pd.DataFrame
        產業資金流向摘要
    """
    data = []
    for flow in flows.values():
        data.append({
            'category': flow.category,
            'foreign_net': flow.foreign_net,
            'investment_trust_net': flow.investment_trust_net,
            'dealer_net': flow.dealer_net,
            'total_net': flow.total_net,
        })

    df = pd.DataFrame(data)

    if len(df) == 0:
        return pd.DataFrame()

    summary = df.groupby('category').agg({
        'foreign_net': 'sum',
        'investment_trust_net': 'sum',
        'dealer_net': 'sum',
        'total_net': 'sum',
    }).reset_index()

    summary.columns = ['產業', '外資', '投信', '自營商', '合計']
    summary = summary.sort_values('合計', ascending=False)

    return summary


def calculate_flow_trend(
    foreign_df: pd.DataFrame,
    investment_trust_df: pd.DataFrame,
    dealer_df: pd.DataFrame,
    days: int = 20,
) -> pd.DataFrame:
    """
    計算三大法人買賣超趨勢

    Parameters:
    -----------
    foreign_df : pd.DataFrame
        外資買賣超資料
    investment_trust_df : pd.DataFrame
        投信買賣超資料
    dealer_df : pd.DataFrame
        自營商買賣超資料
    days : int
        天數

    Returns:
    --------
    pd.DataFrame
        每日三大法人總買賣超
    """
    result = pd.DataFrame()

    if foreign_df is not None and len(foreign_df) > 0:
        result['外資'] = foreign_df.tail(days).sum(axis=1) / 1000  # 轉換為張

    if investment_trust_df is not None and len(investment_trust_df) > 0:
        result['投信'] = investment_trust_df.tail(days).sum(axis=1) / 1000

    if dealer_df is not None and len(dealer_df) > 0:
        result['自營商'] = dealer_df.tail(days).sum(axis=1) / 1000

    if len(result) > 0:
        result['合計'] = result.sum(axis=1)

    return result


def get_continuous_buy_stocks(
    flows: Dict[str, InstitutionalFlow],
    min_days: int = 3,
    flow_type: str = 'foreign',
) -> List[InstitutionalFlow]:
    """
    取得連續買超股票

    Parameters:
    -----------
    flows : Dict[str, InstitutionalFlow]
        法人買賣超資料
    min_days : int
        最少連續天數
    flow_type : str
        'foreign' 外資連續買超

    Returns:
    --------
    List[InstitutionalFlow]
        連續買超股票列表
    """
    result = []

    for flow in flows.values():
        if flow.consecutive_days >= min_days:
            result.append(flow)

    # 按連續天數排序
    result.sort(key=lambda x: x.consecutive_days, reverse=True)

    return result
