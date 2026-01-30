"""
社群媒體掃描模組 - X (Twitter) 台股討論分析
"""
import re
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter
import json

# 載入環境變數
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

from core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SocialPost:
    """社群貼文"""
    text: str
    author: str
    created_at: datetime
    platform: str  # 'x', 'threads', 'ptt'
    url: str = ''
    likes: int = 0
    retweets: int = 0
    stocks: List[str] = field(default_factory=list)
    sentiment: str = 'neutral'


class XScanner:
    """
    X (Twitter) 台股討論掃描器
    使用 Twitter API v2
    """

    BASE_URL = 'https://api.twitter.com/2'

    def __init__(self):
        self.bearer_token = os.environ.get('X_BEARER_TOKEN', '')
        self.posts_cache: List[SocialPost] = []
        self.cache_file = Path(__file__).parent.parent / 'data' / 'x_cache.json'

        # 台股相關搜尋關鍵字
        self.search_queries = [
            '台股',
            '台積電 OR 2330',
            '鴻海 OR 2317',
            '聯發科 OR 2454',
            '台達電 OR 2308',
            '中華電 OR 2412',
            '富邦金 OR 2881',
            '國泰金 OR 2882',
            '兆豐金 OR 2886',
            '台塑 OR 1301',
            '南亞 OR 1303',
        ]

        # 股票代碼正則表達式
        self.stock_pattern = re.compile(r'\b(\d{4})\b')

        # 情緒關鍵字
        self.positive_keywords = [
            '看多', '做多', '利多', '上漲', '大漲', '噴', '飆', '衝',
            '買進', '加碼', '看好', '強勢', '突破', '創高', '紅K',
            '起漲', '多頭', '主力買', '外資買', '投信買',
        ]
        self.negative_keywords = [
            '看空', '做空', '利空', '下跌', '大跌', '崩', '殺',
            '賣出', '減碼', '看壞', '弱勢', '跌破', '創低', '黑K',
            '出貨', '空頭', '主力賣', '外資賣', '投信賣',
        ]

    def _get_headers(self) -> Dict:
        """取得 API 請求標頭"""
        return {
            'Authorization': f'Bearer {self.bearer_token}',
            'Content-Type': 'application/json',
        }

    def search_tweets(self, query: str, max_results: int = 100) -> List[SocialPost]:
        """
        搜尋推文

        Parameters:
        -----------
        query : str
            搜尋關鍵字
        max_results : int
            最大結果數量 (10-100)

        Returns:
        --------
        List[SocialPost]
            推文列表
        """
        if not self.bearer_token:
            logger.error('X Bearer Token 未設定')
            return []

        url = f'{self.BASE_URL}/tweets/search/recent'

        params = {
            'query': f'{query} -is:retweet lang:zh',  # 排除轉推，只搜中文
            'max_results': min(max_results, 100),
            'tweet.fields': 'created_at,public_metrics,author_id',
            'expansions': 'author_id',
            'user.fields': 'username,name',
        }

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )

            if response.status_code == 401:
                logger.error('X API 認證失敗，請檢查 Bearer Token')
                return []
            elif response.status_code == 402:
                logger.warning('X API 免費額度已用完，請等待下月重置或升級方案')
                return []
            elif response.status_code == 429:
                logger.warning('X API 請求次數超過限制')
                return []
            elif response.status_code != 200:
                logger.error(f'X API 錯誤: {response.status_code} - {response.text}')
                return []

            data = response.json()
            posts = []

            # 建立 author_id -> username 對照
            users = {}
            if 'includes' in data and 'users' in data['includes']:
                for user in data['includes']['users']:
                    users[user['id']] = user.get('username', '')

            for tweet in data.get('data', []):
                # 解析時間
                created_at = datetime.now()
                if tweet.get('created_at'):
                    try:
                        created_at = datetime.fromisoformat(
                            tweet['created_at'].replace('Z', '+00:00')
                        ).replace(tzinfo=None)
                    except Exception:
                        pass

                # 取得作者
                author = users.get(tweet.get('author_id', ''), '')

                # 取得互動數據
                metrics = tweet.get('public_metrics', {})

                post = SocialPost(
                    text=tweet.get('text', ''),
                    author=author,
                    created_at=created_at,
                    platform='x',
                    url=f"https://x.com/{author}/status/{tweet.get('id', '')}",
                    likes=metrics.get('like_count', 0),
                    retweets=metrics.get('retweet_count', 0),
                )

                # 分析股票代碼
                self._analyze_post(post)
                posts.append(post)

            logger.info(f'X 搜尋 "{query}": 取得 {len(posts)} 則推文')
            return posts

        except Exception as e:
            logger.error(f'X API 搜尋失敗: {e}')
            return []

    def _analyze_post(self, post: SocialPost):
        """分析貼文內容"""
        text = post.text

        # 提取股票代碼 (4位數字)
        stocks = self.stock_pattern.findall(text)
        # 過濾有效的股票代碼 (1000-9999)
        valid_stocks = [s for s in stocks if 1000 <= int(s) <= 9999]
        post.stocks = list(set(valid_stocks))

        # 情緒分析
        positive_count = sum(1 for kw in self.positive_keywords if kw in text)
        negative_count = sum(1 for kw in self.negative_keywords if kw in text)

        if positive_count > negative_count:
            post.sentiment = 'positive'
        elif negative_count > positive_count:
            post.sentiment = 'negative'
        else:
            post.sentiment = 'neutral'

    def fetch_all(self) -> List[SocialPost]:
        """
        抓取所有台股相關推文

        Returns:
        --------
        List[SocialPost]
            所有推文列表
        """
        all_posts = []

        for query in self.search_queries:
            posts = self.search_tweets(query, max_results=50)
            all_posts.extend(posts)

        # 去重 (根據 URL)
        seen_urls = set()
        unique_posts = []
        for post in all_posts:
            if post.url not in seen_urls:
                seen_urls.add(post.url)
                unique_posts.append(post)

        # 按時間排序
        unique_posts.sort(key=lambda x: x.created_at, reverse=True)

        self.posts_cache = unique_posts
        self._save_cache()

        logger.info(f'X 共取得 {len(unique_posts)} 則不重複推文')
        return unique_posts

    def get_hot_stocks(self, hours: int = 24) -> Dict[str, int]:
        """
        取得熱門股票討論排行

        Parameters:
        -----------
        hours : int
            最近幾小時

        Returns:
        --------
        Dict[str, int]
            股票代碼 -> 討論次數
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        stock_counter = Counter()

        for post in self.posts_cache:
            if post.created_at >= cutoff:
                for stock in post.stocks:
                    stock_counter[stock] += 1

        return dict(stock_counter.most_common(20))

    def get_stock_sentiment(self, stock_id: str, hours: int = 24) -> Dict:
        """
        取得特定股票的社群情緒

        Parameters:
        -----------
        stock_id : str
            股票代碼
        hours : int
            最近幾小時

        Returns:
        --------
        Dict
            情緒統計
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        posts = [
            p for p in self.posts_cache
            if stock_id in p.stocks and p.created_at >= cutoff
        ]

        positive = sum(1 for p in posts if p.sentiment == 'positive')
        negative = sum(1 for p in posts if p.sentiment == 'negative')
        neutral = sum(1 for p in posts if p.sentiment == 'neutral')

        return {
            'stock_id': stock_id,
            'total_posts': len(posts),
            'positive': positive,
            'negative': negative,
            'neutral': neutral,
            'sentiment_score': positive - negative,
            'posts': posts[:10],  # 最新 10 則
        }

    def _save_cache(self):
        """儲存快取"""
        try:
            self.cache_file.parent.mkdir(exist_ok=True)
            cache_data = {
                'updated_at': datetime.now().isoformat(),
                'posts': [
                    {
                        'text': p.text,
                        'author': p.author,
                        'created_at': p.created_at.isoformat(),
                        'platform': p.platform,
                        'url': p.url,
                        'likes': p.likes,
                        'retweets': p.retweets,
                        'stocks': p.stocks,
                        'sentiment': p.sentiment,
                    }
                    for p in self.posts_cache
                ]
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f'X 快取已儲存: {len(self.posts_cache)} 則')
        except Exception as e:
            logger.error(f'儲存 X 快取失敗: {e}')

    def load_cache(self) -> List[SocialPost]:
        """載入快取"""
        if not self.cache_file.exists():
            return []

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            posts = []
            for p in cache_data.get('posts', []):
                posts.append(SocialPost(
                    text=p['text'],
                    author=p['author'],
                    created_at=datetime.fromisoformat(p['created_at']),
                    platform=p['platform'],
                    url=p.get('url', ''),
                    likes=p.get('likes', 0),
                    retweets=p.get('retweets', 0),
                    stocks=p.get('stocks', []),
                    sentiment=p.get('sentiment', 'neutral'),
                ))

            self.posts_cache = posts
            logger.info(f'X 快取已載入: {len(posts)} 則')
            return posts

        except Exception as e:
            logger.error(f'載入 X 快取失敗: {e}')
            return []


# 測試用
if __name__ == '__main__':
    scanner = XScanner()
    if scanner.bearer_token:
        posts = scanner.search_tweets('台股', max_results=10)
        for p in posts[:5]:
            print(f'[{p.sentiment}] @{p.author}: {p.text[:50]}...')
            print(f'  股票: {p.stocks}, 讚: {p.likes}')
            print()
    else:
        print('請設定 X_BEARER_TOKEN 環境變數')
