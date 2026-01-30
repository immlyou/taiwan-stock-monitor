# -*- coding: utf-8 -*-
"""
熱門股票整合分析模組

結合三大面向產生需要關注的熱門股票：
1. 新聞熱度 - 近期新聞提及次數與情緒分數
2. 成交量異常 - 近期成交量相對於過去平均值
3. 價格動能 - 近期價格變動趨勢

用於每日晨報功能
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import get_loader


@dataclass
class HotStockScore:
    """熱門股票評分結構"""
    stock_id: str
    name: str
    industry: str

    # 綜合分數 (0-100)
    total_score: float

    # 各項分數 (0-100)
    news_score: float = 0.0        # 新聞熱度分數
    volume_score: float = 0.0      # 成交量異常分數
    momentum_score: float = 0.0    # 價格動能分數

    # 詳細資訊
    news_count: int = 0            # 新聞數量
    news_sentiment: float = 0.0    # 新聞情緒 (-1 ~ 1)
    volume_ratio: float = 1.0      # 成交量倍數 (vs 20日均量)
    price_change_5d: float = 0.0   # 5日漲跌幅 (%)
    price_change_20d: float = 0.0  # 20日漲跌幅 (%)
    current_price: float = 0.0     # 現價

    # 標籤
    tags: List[str] = field(default_factory=list)

    @property
    def is_high_volume(self) -> bool:
        """成交量是否異常放大"""
        return self.volume_ratio >= 2.0

    @property
    def is_positive_news(self) -> bool:
        """新聞情緒是否正面"""
        return self.news_sentiment > 0.2

    @property
    def is_negative_news(self) -> bool:
        """新聞情緒是否負面"""
        return self.news_sentiment < -0.2

    @property
    def trend_direction(self) -> str:
        """趨勢方向"""
        if self.price_change_5d > 3:
            return "強勢上漲"
        elif self.price_change_5d > 0:
            return "溫和上漲"
        elif self.price_change_5d > -3:
            return "溫和下跌"
        else:
            return "明顯下跌"


class HotStockAnalyzer:
    """
    熱門股票分析器

    整合新聞、成交量、價格動能三大面向
    """

    def __init__(
        self,
        news_weight: float = 0.4,
        volume_weight: float = 0.3,
        momentum_weight: float = 0.3,
    ):
        """
        Parameters:
        -----------
        news_weight : float
            新聞熱度權重 (預設 0.4)
        volume_weight : float
            成交量異常權重 (預設 0.3)
        momentum_weight : float
            價格動能權重 (預設 0.3)
        """
        self.news_weight = news_weight
        self.volume_weight = volume_weight
        self.momentum_weight = momentum_weight

        self.loader = get_loader()

    def calculate_volume_scores(
        self,
        stock_ids: Optional[List[str]] = None,
        lookback_days: int = 5,
        avg_days: int = 20,
    ) -> Dict[str, Dict]:
        """
        計算成交量異常分數

        Parameters:
        -----------
        stock_ids : List[str], optional
            要分析的股票列表，None 表示分析所有股票
        lookback_days : int
            觀察近幾日成交量
        avg_days : int
            平均成交量計算天數

        Returns:
        --------
        Dict[str, Dict]
            {stock_id: {'volume_ratio': float, 'score': float}}
        """
        try:
            volume = self.loader.get('volume')
        except Exception:
            return {}

        if stock_ids is None:
            stock_ids = volume.columns.tolist()

        results = {}

        for stock_id in stock_ids:
            if stock_id not in volume.columns:
                continue

            stock_vol = volume[stock_id].dropna()
            if len(stock_vol) < avg_days + lookback_days:
                continue

            # 近期平均成交量
            recent_vol = stock_vol.iloc[-lookback_days:].mean()

            # 過去平均成交量 (排除最近幾天)
            past_vol = stock_vol.iloc[-(avg_days + lookback_days):-lookback_days].mean()

            if past_vol <= 0:
                continue

            volume_ratio = recent_vol / past_vol

            # 轉換為分數 (0-100)
            # volume_ratio = 1.0 時分數 = 50
            # volume_ratio = 2.0 時分數 = 75
            # volume_ratio = 3.0 時分數 = 90
            # volume_ratio >= 5.0 時分數 = 100
            if volume_ratio >= 5.0:
                score = 100
            elif volume_ratio >= 1.0:
                score = 50 + (volume_ratio - 1.0) * 12.5
            else:
                score = max(0, volume_ratio * 50)

            results[stock_id] = {
                'volume_ratio': volume_ratio,
                'score': min(100, score),
                'recent_volume': recent_vol,
                'avg_volume': past_vol,
            }

        return results

    def calculate_momentum_scores(
        self,
        stock_ids: Optional[List[str]] = None,
    ) -> Dict[str, Dict]:
        """
        計算價格動能分數

        Parameters:
        -----------
        stock_ids : List[str], optional
            要分析的股票列表

        Returns:
        --------
        Dict[str, Dict]
            {stock_id: {'price_change_5d': float, 'price_change_20d': float, 'score': float}}
        """
        try:
            close = self.loader.get('close')
        except Exception:
            return {}

        if stock_ids is None:
            stock_ids = close.columns.tolist()

        results = {}

        for stock_id in stock_ids:
            if stock_id not in close.columns:
                continue

            stock_price = close[stock_id].dropna()
            if len(stock_price) < 21:
                continue

            current_price = stock_price.iloc[-1]
            price_5d_ago = stock_price.iloc[-6] if len(stock_price) >= 6 else stock_price.iloc[0]
            price_20d_ago = stock_price.iloc[-21] if len(stock_price) >= 21 else stock_price.iloc[0]

            change_5d = (current_price / price_5d_ago - 1) * 100 if price_5d_ago > 0 else 0
            change_20d = (current_price / price_20d_ago - 1) * 100 if price_20d_ago > 0 else 0

            # 動能分數計算
            # 結合短期和中期漲幅
            # 短期漲幅權重較高
            raw_score = change_5d * 0.6 + change_20d * 0.4

            # 正規化到 0-100
            # 漲幅 10% 對應分數 75
            # 漲幅 20% 對應分數 90
            # 漲幅 >= 30% 對應分數 100
            # 跌幅處理類似
            if raw_score >= 30:
                score = 100
            elif raw_score >= 0:
                score = 50 + raw_score * (50 / 30)
            elif raw_score >= -30:
                score = 50 + raw_score * (50 / 30)
            else:
                score = 0

            results[stock_id] = {
                'current_price': current_price,
                'price_change_5d': change_5d,
                'price_change_20d': change_20d,
                'score': max(0, min(100, score)),
            }

        return results

    def analyze_hot_stocks(
        self,
        news_hot_stocks: Optional[Dict[str, Dict]] = None,
        top_n: int = 20,
        min_score: float = 50.0,
    ) -> List[HotStockScore]:
        """
        整合分析熱門股票

        Parameters:
        -----------
        news_hot_stocks : Dict[str, Dict], optional
            新聞熱度資料，格式為 {stock_id: {'count': int, 'sentiment': float, 'score': float}}
            可從 NewsScanner.get_hot_stocks() 取得
        top_n : int
            回傳前 N 名
        min_score : float
            最低分數門檻

        Returns:
        --------
        List[HotStockScore]
            排序後的熱門股票列表
        """
        # 取得股票資訊
        try:
            stock_info = self.loader.get_stock_info()
            stock_info_dict = {
                row['stock_id']: {
                    'name': row.get('name', ''),
                    'industry': row.get('industry', row.get('category', '')),
                }
                for _, row in stock_info.iterrows()
            }
        except Exception:
            stock_info_dict = {}

        # 收集所有相關股票
        all_stocks = set()

        if news_hot_stocks:
            all_stocks.update(news_hot_stocks.keys())

        # 計算成交量和動能分數
        volume_scores = self.calculate_volume_scores(list(all_stocks) if all_stocks else None)
        momentum_scores = self.calculate_momentum_scores(list(all_stocks) if all_stocks else None)

        # 補充成交量異常股票
        high_volume_stocks = [
            sid for sid, data in volume_scores.items()
            if data['volume_ratio'] >= 1.5
        ]
        all_stocks.update(high_volume_stocks[:50])  # 最多加 50 支

        # 重新計算 (如果有新股票加入)
        if len(all_stocks) > len(volume_scores):
            volume_scores = self.calculate_volume_scores(list(all_stocks))
            momentum_scores = self.calculate_momentum_scores(list(all_stocks))

        # 整合計算
        results = []

        for stock_id in all_stocks:
            # 取得各項分數
            news_data = news_hot_stocks.get(stock_id, {}) if news_hot_stocks else {}
            vol_data = volume_scores.get(stock_id, {})
            mom_data = momentum_scores.get(stock_id, {})

            news_score = news_data.get('score', 0)
            volume_score = vol_data.get('score', 50)  # 沒有資料時給中間值
            momentum_score = mom_data.get('score', 50)

            # 計算綜合分數
            total_score = (
                news_score * self.news_weight +
                volume_score * self.volume_weight +
                momentum_score * self.momentum_weight
            )

            if total_score < min_score:
                continue

            # 取得股票資訊
            info = stock_info_dict.get(stock_id, {})

            # 建立標籤
            tags = []
            if news_data.get('count', 0) >= 3:
                tags.append('新聞熱門')
            if news_data.get('sentiment', 0) > 0.3:
                tags.append('正面報導')
            elif news_data.get('sentiment', 0) < -0.3:
                tags.append('負面報導')
            if vol_data.get('volume_ratio', 1) >= 2.0:
                tags.append('爆量')
            elif vol_data.get('volume_ratio', 1) >= 1.5:
                tags.append('量增')
            if mom_data.get('price_change_5d', 0) >= 5:
                tags.append('短線強勢')
            elif mom_data.get('price_change_5d', 0) <= -5:
                tags.append('短線弱勢')

            results.append(HotStockScore(
                stock_id=stock_id,
                name=info.get('name', ''),
                industry=info.get('industry', ''),
                total_score=total_score,
                news_score=news_score,
                volume_score=volume_score,
                momentum_score=momentum_score,
                news_count=news_data.get('count', 0),
                news_sentiment=news_data.get('sentiment', 0),
                volume_ratio=vol_data.get('volume_ratio', 1.0),
                price_change_5d=mom_data.get('price_change_5d', 0),
                price_change_20d=mom_data.get('price_change_20d', 0),
                current_price=mom_data.get('current_price', 0),
                tags=tags,
            ))

        # 排序
        results.sort(key=lambda x: x.total_score, reverse=True)

        return results[:top_n]

    def get_volume_anomalies(
        self,
        min_ratio: float = 2.0,
        top_n: int = 20,
    ) -> List[Dict]:
        """
        取得成交量異常股票

        Parameters:
        -----------
        min_ratio : float
            最低成交量倍數
        top_n : int
            回傳前 N 名

        Returns:
        --------
        List[Dict]
            成交量異常股票列表
        """
        volume_scores = self.calculate_volume_scores()
        momentum_scores = self.calculate_momentum_scores()

        # 取得股票資訊
        try:
            stock_info = self.loader.get_stock_info()
            stock_info_dict = {
                row['stock_id']: row.get('name', '')
                for _, row in stock_info.iterrows()
            }
        except Exception:
            stock_info_dict = {}

        # 篩選異常
        anomalies = []
        for stock_id, data in volume_scores.items():
            if data['volume_ratio'] >= min_ratio:
                mom_data = momentum_scores.get(stock_id, {})
                anomalies.append({
                    'stock_id': stock_id,
                    'name': stock_info_dict.get(stock_id, ''),
                    'volume_ratio': data['volume_ratio'],
                    'price_change_5d': mom_data.get('price_change_5d', 0),
                    'current_price': mom_data.get('current_price', 0),
                })

        # 按成交量倍數排序
        anomalies.sort(key=lambda x: x['volume_ratio'], reverse=True)

        return anomalies[:top_n]

    def generate_focus_report(
        self,
        news_hot_stocks: Optional[Dict[str, Dict]] = None,
    ) -> Dict:
        """
        產生需要關注股票報告

        Parameters:
        -----------
        news_hot_stocks : Dict[str, Dict], optional
            新聞熱度資料

        Returns:
        --------
        Dict
            報告內容，包含各類別熱門股票
        """
        hot_stocks = self.analyze_hot_stocks(news_hot_stocks, top_n=30, min_score=40)
        volume_anomalies = self.get_volume_anomalies(min_ratio=2.0, top_n=10)

        # 分類
        positive_sentiment = [s for s in hot_stocks if s.is_positive_news]
        negative_sentiment = [s for s in hot_stocks if s.is_negative_news]
        high_volume = [s for s in hot_stocks if s.is_high_volume]
        strong_momentum = [s for s in hot_stocks if s.price_change_5d >= 5]

        return {
            'hot_stocks': hot_stocks[:20],
            'positive_sentiment': positive_sentiment[:10],
            'negative_sentiment': negative_sentiment[:10],
            'high_volume': high_volume[:10],
            'strong_momentum': strong_momentum[:10],
            'volume_anomalies': volume_anomalies,
            'summary': {
                'total_analyzed': len(hot_stocks),
                'positive_count': len(positive_sentiment),
                'negative_count': len(negative_sentiment),
                'high_volume_count': len(high_volume),
            },
        }


def get_hot_stocks_integrated(
    news_scanner=None,
    hours: int = 24,
    top_n: int = 20,
) -> List[HotStockScore]:
    """
    整合取得熱門股票 (便利函數)

    Parameters:
    -----------
    news_scanner : NewsScanner, optional
        新聞掃描器實例，如果沒有會自動建立
    hours : int
        新聞時間範圍 (小時)
    top_n : int
        回傳前 N 名

    Returns:
    --------
    List[HotStockScore]
        熱門股票列表
    """
    # 取得新聞熱度資料
    news_hot_stocks = None
    if news_scanner is not None:
        try:
            news_hot_list = news_scanner.get_hot_stocks(hours=hours, top_n=50)
            news_hot_stocks = {
                item['stock_id']: {
                    'count': item['mention_count'],
                    'sentiment': item['avg_sentiment'],
                    'score': min(100, item['mention_count'] * 15 + abs(item['avg_sentiment']) * 30),
                }
                for item in news_hot_list
            }
        except Exception:
            pass

    # 分析
    analyzer = HotStockAnalyzer()
    return analyzer.analyze_hot_stocks(news_hot_stocks, top_n=top_n)


# 測試
if __name__ == '__main__':
    print("測試熱門股票整合分析模組...")
    print()

    analyzer = HotStockAnalyzer()

    # 測試成交量分數
    print("【成交量異常股票 Top 10】")
    anomalies = analyzer.get_volume_anomalies(min_ratio=1.5, top_n=10)
    for item in anomalies:
        print(f"  {item['stock_id']} {item['name']}: {item['volume_ratio']:.1f}x, 5日漲跌: {item['price_change_5d']:+.1f}%")

    print()

    # 測試整合分析 (無新聞資料)
    print("【熱門股票 Top 10 (僅量價分析)】")
    hot_stocks = analyzer.analyze_hot_stocks(top_n=10, min_score=30)
    for stock in hot_stocks:
        print(f"  {stock.stock_id} {stock.name}: {stock.total_score:.1f}分, 量比: {stock.volume_ratio:.1f}x, 5日: {stock.price_change_5d:+.1f}%")
        if stock.tags:
            print(f"    標籤: {', '.join(stock.tags)}")
