"""
PTT Stock 版掃描模組 - 台股討論分析
"""
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter
import json
import time

from core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PTTPost:
    """PTT 貼文"""
    title: str
    author: str
    date: str
    url: str
    push_count: int = 0  # 推文數
    stocks: List[str] = field(default_factory=list)
    sentiment: str = 'neutral'
    created_at: datetime = field(default_factory=datetime.now)


class PTTScanner:
    """
    PTT Stock 版掃描器
    透過 PTT 網頁版抓取討論
    """

    BASE_URL = 'https://www.ptt.cc'
    BOARD_URL = 'https://www.ptt.cc/bbs/Stock/index.html'

    def __init__(self):
        self.posts_cache: List[PTTPost] = []
        self.cache_file = Path(__file__).parent.parent / 'data' / 'ptt_cache.json'

        # 股票代碼正則表達式
        self.stock_pattern = re.compile(r'\b(\d{4})\b')

        # 情緒關鍵字
        self.positive_keywords = [
            '多', '買', '漲', '噴', '飆', '衝', '強', '讚', '推',
            '利多', '看好', '加碼', '進場', '起飛', '突破', '創高',
            '主力買', '外資買', '投信買', '紅K', '長紅',
        ]
        self.negative_keywords = [
            '空', '賣', '跌', '崩', '殺', '弱', '慘', '噓',
            '利空', '看壞', '減碼', '出場', '套牢', '跌破', '創低',
            '主力賣', '外資賣', '投信賣', '黑K', '長黑',
        ]

        # 請求 session (處理 over18 cookie)
        self.session = requests.Session()
        self.session.cookies.set('over18', '1')

        # 設定更完整的 headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def fetch_posts(self, pages: int = 5) -> List[PTTPost]:
        """
        抓取 PTT Stock 版文章

        Parameters:
        -----------
        pages : int
            抓取頁數 (每頁約 20 篇)

        Returns:
        --------
        List[PTTPost]
            文章列表
        """
        all_posts = []
        url = self.BOARD_URL

        for page in range(pages):
            try:
                response = self.session.get(url, headers=self.headers, timeout=30)

                if response.status_code != 200:
                    logger.error(f'PTT 請求失敗: {response.status_code}')
                    break

                soup = BeautifulSoup(response.text, 'html.parser')

                # 取得文章列表
                articles = soup.select('div.r-ent')

                for article in articles:
                    try:
                        # 標題
                        title_elem = article.select_one('div.title a')
                        if not title_elem:
                            continue

                        title = title_elem.text.strip()
                        link = self.BASE_URL + title_elem['href']

                        # 作者
                        author_elem = article.select_one('div.meta div.author')
                        author = author_elem.text.strip() if author_elem else ''

                        # 日期
                        date_elem = article.select_one('div.meta div.date')
                        date_str = date_elem.text.strip() if date_elem else ''

                        # 推文數
                        push_elem = article.select_one('div.nrec span')
                        push_count = 0
                        if push_elem:
                            push_text = push_elem.text.strip()
                            if push_text == '爆':
                                push_count = 100
                            elif push_text.startswith('X'):
                                push_count = -10
                            elif push_text.isdigit():
                                push_count = int(push_text)

                        # 建立貼文物件
                        post = PTTPost(
                            title=title,
                            author=author,
                            date=date_str,
                            url=link,
                            push_count=push_count,
                            created_at=self._parse_date(date_str),
                        )

                        # 分析貼文
                        self._analyze_post(post)
                        all_posts.append(post)

                    except Exception as e:
                        logger.debug(f'解析文章失敗: {e}')
                        continue

                # 取得上一頁連結
                prev_link = soup.select_one('div.btn-group-paging a:nth-child(2)')
                if prev_link and 'href' in prev_link.attrs:
                    url = self.BASE_URL + prev_link['href']
                else:
                    break

                # 避免請求過快
                time.sleep(0.5)

            except Exception as e:
                logger.error(f'抓取 PTT 頁面失敗: {e}')
                break

        # 更新快取
        self.posts_cache = all_posts
        self._save_cache()

        logger.info(f'PTT Stock 版共取得 {len(all_posts)} 篇文章')
        return all_posts

    def _parse_date(self, date_str: str) -> datetime:
        """解析 PTT 日期格式 (M/DD)"""
        try:
            now = datetime.now()
            month, day = date_str.strip().split('/')
            parsed = datetime(now.year, int(month), int(day))
            # 如果解析出的日期在未來，表示是去年
            if parsed > now:
                parsed = datetime(now.year - 1, int(month), int(day))
            return parsed
        except Exception:
            return datetime.now()

    def _analyze_post(self, post: PTTPost):
        """分析貼文內容"""
        title = post.title

        # 提取股票代碼
        stocks = self.stock_pattern.findall(title)
        valid_stocks = [s for s in stocks if 1000 <= int(s) <= 9999]
        post.stocks = list(set(valid_stocks))

        # 情緒分析
        positive_count = sum(1 for kw in self.positive_keywords if kw in title)
        negative_count = sum(1 for kw in self.negative_keywords if kw in title)

        # 也考慮推文數
        if post.push_count >= 50:
            positive_count += 2
        elif post.push_count <= -5:
            negative_count += 2

        if positive_count > negative_count:
            post.sentiment = 'positive'
        elif negative_count > positive_count:
            post.sentiment = 'negative'
        else:
            post.sentiment = 'neutral'

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
            'posts': posts[:10],
        }

    def _save_cache(self):
        """儲存快取"""
        try:
            self.cache_file.parent.mkdir(exist_ok=True)
            cache_data = {
                'updated_at': datetime.now().isoformat(),
                'posts': [
                    {
                        'title': p.title,
                        'author': p.author,
                        'date': p.date,
                        'url': p.url,
                        'push_count': p.push_count,
                        'stocks': p.stocks,
                        'sentiment': p.sentiment,
                        'created_at': p.created_at.isoformat(),
                    }
                    for p in self.posts_cache
                ]
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f'PTT 快取已儲存: {len(self.posts_cache)} 篇')
        except Exception as e:
            logger.error(f'儲存 PTT 快取失敗: {e}')

    def load_cache(self) -> List[PTTPost]:
        """載入快取"""
        if not self.cache_file.exists():
            return []

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            posts = []
            for p in cache_data.get('posts', []):
                posts.append(PTTPost(
                    title=p['title'],
                    author=p['author'],
                    date=p['date'],
                    url=p.get('url', ''),
                    push_count=p.get('push_count', 0),
                    stocks=p.get('stocks', []),
                    sentiment=p.get('sentiment', 'neutral'),
                    created_at=datetime.fromisoformat(p['created_at']),
                ))

            self.posts_cache = posts
            logger.info(f'PTT 快取已載入: {len(posts)} 篇')
            return posts

        except Exception as e:
            logger.error(f'載入 PTT 快取失敗: {e}')
            return []


# 測試用
if __name__ == '__main__':
    scanner = PTTScanner()
    posts = scanner.fetch_posts(pages=2)
    print(f'取得 {len(posts)} 篇文章')
    for p in posts[:5]:
        print(f'[{p.sentiment}] {p.title[:40]}... (推:{p.push_count})')
        if p.stocks:
            print(f'  股票: {p.stocks}')
