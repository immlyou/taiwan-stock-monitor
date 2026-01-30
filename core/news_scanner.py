# -*- coding: utf-8 -*-
"""
新聞掃描模組 - RSS Feed 整合與股票新聞分析 (優化版)

改進項目:
1. 股票識別: 正則邊界匹配、排除誤判
2. 情緒分析: 否定詞處理、關鍵字權重、提高閾值
3. 熱門計算: 同事件去重、時間衰減、來源權重
4. 新增功能: 自選股整合、趨勢分析
"""
import re
import json
import hashlib
import feedparser
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class NewsItem:
    """新聞項目"""
    title: str
    link: str
    source: str
    published: datetime
    summary: str = ''
    stocks: List[str] = field(default_factory=list)
    sentiment: str = 'neutral'  # positive, negative, neutral
    sentiment_score: float = 0.0  # -1.0 ~ 1.0
    keywords: List[str] = field(default_factory=list)
    content_hash: str = ''  # 用於去重

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'link': self.link,
            'source': self.source,
            'published': self.published.isoformat(),
            'summary': self.summary,
            'stocks': self.stocks,
            'sentiment': self.sentiment,
            'sentiment_score': self.sentiment_score,
            'keywords': self.keywords,
            'content_hash': self.content_hash,
        }


# RSS Feed 來源設定 (加入權重)
RSS_FEEDS = {
    # ===== Yahoo 奇摩股市 =====
    'yahoo_news': {
        'name': 'Yahoo 最新新聞',
        'url': 'https://tw.stock.yahoo.com/rss?category=news',
        'category': 'news',
        'weight': 1.0,  # 來源權重
    },
    'yahoo_tw_market': {
        'name': 'Yahoo 台股動態',
        'url': 'https://tw.stock.yahoo.com/rss?category=tw-market',
        'category': 'market',
        'weight': 1.2,
    },
    'yahoo_intl': {
        'name': 'Yahoo 國際財經',
        'url': 'https://tw.stock.yahoo.com/rss?category=intl-markets',
        'category': 'international',
        'weight': 0.8,
    },

    # ===== 聯合新聞網 =====
    'udn_stock': {
        'name': '聯合新聞 股市',
        'url': 'https://money.udn.com/rssfeed/news/1001/5641?ch=money',
        'category': 'market',
        'weight': 1.0,
    },

    # ===== 中央社 =====
    'cna_finance': {
        'name': '中央社 財經',
        'url': 'https://feeds.feedburner.com/rsscna/finance?format=xml',
        'category': 'news',
        'weight': 1.3,  # 官方媒體權重較高
    },

    # ===== 自由時報 =====
    'ltn_business': {
        'name': '自由時報 財經',
        'url': 'https://news.ltn.com.tw/rss/business.xml',
        'category': 'news',
        'weight': 1.0,
    },

    # ===== 天下雜誌 =====
    'cw_content': {
        'name': '天下雜誌',
        'url': 'https://www.cw.com.tw/RSS/cw_content.xml',
        'category': 'column',
        'weight': 0.9,
    },

    # ===== 金管會 (高權重) =====
    'fsc_news': {
        'name': '金管會 新聞稿',
        'url': 'https://www.fsc.gov.tw/RSS/Messages?language=chinese&serno=201202290001',
        'category': 'regulation',
        'weight': 1.5,  # 官方公告權重最高
    },
    'fsc_policy': {
        'name': '金管會 政策消息',
        'url': 'https://www.fsc.gov.tw/RSS/Messages?language=chinese&serno=201202290009',
        'category': 'regulation',
        'weight': 1.5,
    },

    # ===== 證期局 =====
    'sfb_news': {
        'name': '證期局 新聞稿',
        'url': 'https://www.sfb.gov.tw/RSS/sfb/Messages?language=chinese&serno=201501270006',
        'category': 'regulation',
        'weight': 1.5,
    },

    # ===== 美股新聞 =====
    'yahoo_us_market': {
        'name': 'Yahoo 美股市場',
        'url': 'https://tw.stock.yahoo.com/rss?category=us-market',
        'category': 'us_stock',
        'weight': 0.8,
    },

    # ===== 鉅亨網 =====
    'cnyes_us': {
        'name': '鉅亨網 美股',
        'url': 'https://news.cnyes.com/api/v3/news/category/us_stock?limit=30',
        'category': 'us_stock',
        'is_json': True,
        'weight': 0.9,
    },
    'cnyes_tw': {
        'name': '鉅亨網 台股',
        'url': 'https://news.cnyes.com/api/v3/news/category/tw_stock?limit=30',
        'category': 'market',
        'is_json': True,
        'weight': 1.1,
    },

    # ===== MoneyDJ =====
    'moneydj_us': {
        'name': 'MoneyDJ 美股',
        'url': 'https://www.moneydj.com/KMDJ/RssCenter.aspx?svc=NR&fno=100&arg=MB07',
        'category': 'us_stock',
        'weight': 0.9,
    },
}


# ========== 情緒分析關鍵字 (加入權重) ==========

POSITIVE_KEYWORDS = {
    # 強利多 (權重 2.0)
    '漲停': 2.0, '創新高': 2.0, '大漲': 2.0, '飆漲': 2.0, '噴出': 2.0,
    '轉盈': 2.0, '獲利創高': 2.0, '營收創高': 2.0, '超預期': 2.0, '優於預期': 2.0,
    '目標價調升': 2.0, '評等調升': 2.0, '法說利多': 2.0,

    # 中度利多 (權重 1.5)
    '利多': 1.5, '看好': 1.5, '上漲': 1.5, '成長': 1.5, '獲利': 1.5,
    '營收增': 1.5, '年增': 1.5, '季增': 1.5, '月增': 1.5, '買進': 1.5,
    '加碼': 1.5, '擴產': 1.5, '訂單': 1.5, '出貨': 1.5, '突破': 1.5,
    '反彈': 1.5, '回升': 1.5, '強勢': 1.5,

    # 輕微利多 (權重 1.0)
    '動能': 1.0, '題材': 1.0, '熱門': 1.0, '紅盤': 1.0, '投資': 1.0,
    '股利': 1.0, '配息': 1.0, '殖利率': 1.0, '業績': 1.0,

    # 美股利多
    '道瓊上漲': 1.5, '那斯達克漲': 1.5, 'S&P漲': 1.5, '費半漲': 1.5,
    '降息': 1.5, 'AI概念': 1.0,
}

NEGATIVE_KEYWORDS = {
    # 強利空 (權重 2.0)
    '跌停': 2.0, '創新低': 2.0, '大跌': 2.0, '重挫': 2.0, '崩盤': 2.0,
    '轉虧': 2.0, '獲利衰退': 2.0, '營收衰退': 2.0, '低於預期': 2.0, '遜於預期': 2.0,
    '目標價調降': 2.0, '評等調降': 2.0, '警示': 2.0,

    # 中度利空 (權重 1.5)
    '利空': 1.5, '看淡': 1.5, '下跌': 1.5, '衰退': 1.5, '虧損': 1.5,
    '營收減': 1.5, '年減': 1.5, '季減': 1.5, '月減': 1.5, '賣出': 1.5,
    '減碼': 1.5, '減產': 1.5, '砍單': 1.5, '庫存': 1.5, '跌破': 1.5,
    '破底': 1.5, '下殺': 1.5, '疲軟': 1.5,

    # 輕微利空 (權重 1.0)
    '風險': 1.0, '警訊': 1.0, '綠盤': 1.0, '萎縮': 1.0, '低迷': 1.0,
    '觀望': 1.0, '保守': 1.0, '撤資': 1.0,

    # 美股利空
    '道瓊下跌': 1.5, '那斯達克跌': 1.5, 'S&P跌': 1.5, '費半跌': 1.5,
    '升息': 1.5, '衰退疑慮': 1.5, '裁員': 1.0,
}

# 否定詞 (會反轉後續關鍵字的情緒)
NEGATION_WORDS = [
    '不', '未', '沒', '無', '難', '非', '否認', '否定', '不會', '未必',
    '難以', '無法', '不再', '尚未', '並非', '不見得', '不一定',
]


class NewsScanner:
    """
    新聞掃描器 (優化版)

    功能:
    - 從多個 RSS Feed 抓取新聞
    - 精確識別新聞中提到的股票
    - 加權情緒分析
    - 智慧熱門股票計算 (去重、時間衰減)
    - 自選股整合
    """

    def __init__(self, stock_info_df=None):
        """
        Parameters:
        -----------
        stock_info_df : pd.DataFrame, optional
            股票資訊 DataFrame，包含 stock_id 和 name
        """
        self.stock_info = stock_info_df
        self.stock_patterns = self._build_stock_patterns()
        self.news_cache: List[NewsItem] = []
        self.cache_file = Path(__file__).parent.parent / 'data' / 'news_cache.json'
        self.cache_file.parent.mkdir(exist_ok=True)

        # 用於同事件去重
        self._event_clusters: Dict[str, List[NewsItem]] = {}

    def _build_stock_patterns(self) -> Dict[str, Tuple[str, re.Pattern]]:
        """
        建立股票識別模式

        Returns:
        --------
        Dict[str, Tuple[str, re.Pattern]]
            {識別字串: (股票代碼, 正則pattern)}
        """
        patterns = {}

        # 容易在新聞中造成誤判的股票名稱 (新聞來源名稱、常見詞彙等)
        # 這些名稱不會被加入股票識別模式，只能透過代號識別
        excluded_names = {
            '時報',      # 8923 - 常見於「中國時報」「工商時報」「自由時報」
            '中時',      # 可能的簡稱
            '聯合',      # 常見於「聯合報」「聯合新聞網」
            '自由',      # 常見於「自由時報」
            '經濟',      # 常見於「經濟日報」
            '工商',      # 常見於「工商時報」
            '中央',      # 常見於「中央社」
            '大眾',      # 常見詞彙
            '國際',      # 常見詞彙
            '世界',      # 常見詞彙
            '中國',      # 常見詞彙
            '台灣',      # 常見詞彙
            '亞洲',      # 常見詞彙
        }

        if self.stock_info is not None:
            for _, row in self.stock_info.iterrows():
                stock_id = str(row.get('stock_id', ''))
                name = str(row.get('name', ''))

                if stock_id and len(stock_id) == 4 and stock_id.isdigit():
                    # 股票代號: 需要邊界匹配，排除在價格/數字中的誤判
                    # 例如: "2330" 但不匹配 "下跌2330點" 或 "12330"
                    # 特別排除年份誤判: "2025年"、"2024年" 等
                    # 使用 negative lookahead 排除後面接「年」的情況
                    pattern = re.compile(rf'(?<![0-9]){stock_id}(?![0-9年])')
                    patterns[stock_id] = (stock_id, pattern)

                    if name and len(name) >= 2:
                        # 移除常見後綴
                        clean_name = name.replace('-DR', '').replace('*', '').replace('-KY', '').strip()
                        # 檢查是否在排除名單中
                        if len(clean_name) >= 2 and clean_name not in excluded_names:
                            # 公司名稱: 需要完整詞匹配
                            name_pattern = re.compile(rf'(?<![a-zA-Z\u4e00-\u9fff]){re.escape(clean_name)}(?![a-zA-Z\u4e00-\u9fff])')
                            patterns[clean_name] = (stock_id, name_pattern)

        # 常見大型股簡稱對應 (精確匹配)
        common_names = {
            '台積電': '2330', '鴻海': '2317', '聯發科': '2454',
            '台達電': '2308', '中華電': '2412', '台塑': '1301',
            '南亞': '1303', '台化': '1326', '統一': '1216',
            '國泰金': '2882', '富邦金': '2881', '中信金': '2891',
            '兆豐金': '2886', '第一金': '2892', '玉山金': '2884',
            '大立光': '3008', '聯電': '2303', '日月光投控': '3711',
            '廣達': '2382', '華碩': '2357', '宏碁': '2353',
            '緯創': '3231', '仁寶': '2324', '和碩': '4938',
            '長榮': '2603', '陽明': '2609', '萬海': '2615',
            '友達': '2409', '群創': '3481', '瑞昱': '2379',
            '台泥': '1101', '亞泥': '1102', '中鋼': '2002',
            '華南金': '2880', '元大金': '2885', '台新金': '2887',
            '聯詠': '3034', '矽力': '6415', '世芯': '3661',
            '信驊': '5274', '創意': '3443', '祥碩': '5269',
        }

        for name, stock_id in common_names.items():
            name_pattern = re.compile(rf'(?<![a-zA-Z\u4e00-\u9fff]){re.escape(name)}(?![a-zA-Z\u4e00-\u9fff])')
            patterns[name] = (stock_id, name_pattern)

        return patterns

    def _compute_content_hash(self, title: str, summary: str) -> str:
        """計算內容雜湊值用於去重"""
        # 移除空白和標點符號後計算
        content = re.sub(r'[\s\W]+', '', title + summary)
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _extract_stocks(self, text: str) -> List[str]:
        """
        從文本中提取股票代碼

        使用正則邊界匹配，避免誤判
        """
        stocks = set()

        for identifier, (stock_id, pattern) in self.stock_patterns.items():
            if pattern.search(text):
                stocks.add(stock_id)

        return list(stocks)

    def _analyze_sentiment(self, text: str) -> Tuple[str, float, List[str]]:
        """
        加權情緒分析

        Returns:
        --------
        Tuple[str, float, List[str]]
            (情緒標籤, 情緒分數, 關鍵字列表)
        """
        positive_score = 0.0
        negative_score = 0.0
        keywords = []

        # 檢查否定詞位置
        negation_positions = []
        for neg_word in NEGATION_WORDS:
            for match in re.finditer(re.escape(neg_word), text):
                negation_positions.append(match.start())

        def is_negated(pos: int) -> bool:
            """檢查該位置前是否有否定詞 (5個字內)"""
            for neg_pos in negation_positions:
                if 0 < pos - neg_pos <= 5:
                    return True
            return False

        # 計算正面分數
        for kw, weight in POSITIVE_KEYWORDS.items():
            for match in re.finditer(re.escape(kw), text):
                if is_negated(match.start()):
                    # 否定詞後的正面詞變成負面
                    negative_score += weight * 0.8
                else:
                    positive_score += weight
                    if kw not in keywords:
                        keywords.append(kw)

        # 計算負面分數
        for kw, weight in NEGATIVE_KEYWORDS.items():
            for match in re.finditer(re.escape(kw), text):
                if is_negated(match.start()):
                    # 否定詞後的負面詞變成正面
                    positive_score += weight * 0.8
                else:
                    negative_score += weight
                    if kw not in keywords:
                        keywords.append(kw)

        # 計算情緒分數 (-1 ~ 1)
        total = positive_score + negative_score
        if total > 0:
            sentiment_score = (positive_score - negative_score) / total
        else:
            sentiment_score = 0.0

        # 判定情緒標籤 (提高閾值，需要明顯差異)
        if positive_score > negative_score * 1.5 and positive_score >= 2.0:
            sentiment = 'positive'
        elif negative_score > positive_score * 1.5 and negative_score >= 2.0:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        return sentiment, sentiment_score, keywords[:8]

    def _analyze_news(self, news_item: NewsItem):
        """分析新聞內容"""
        text = news_item.title + ' ' + news_item.summary

        # 提取股票
        news_item.stocks = self._extract_stocks(text)

        # 情緒分析
        sentiment, score, keywords = self._analyze_sentiment(text)
        news_item.sentiment = sentiment
        news_item.sentiment_score = score
        news_item.keywords = keywords

        # 計算內容雜湊
        news_item.content_hash = self._compute_content_hash(news_item.title, news_item.summary)

    def fetch_feed(self, feed_key: str) -> List[NewsItem]:
        """抓取單一 RSS Feed"""
        if feed_key not in RSS_FEEDS:
            logger.warning(f'未知的 RSS Feed: {feed_key}')
            return []

        feed_config = RSS_FEEDS[feed_key]
        url = feed_config['url']
        source = feed_config['name']
        is_json = feed_config.get('is_json', False)

        try:
            logger.info(f'抓取新聞來源: {source}')
            response = requests.get(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                },
                timeout=15
            )
            response.raise_for_status()

            news_items = []

            if is_json:
                news_items = self._parse_json_feed(response.json(), source)
            else:
                feed = feedparser.parse(response.text)

                if feed.bozo and feed.bozo_exception:
                    logger.warning(f'RSS 解析警告 ({source}): {feed.bozo_exception}')

                for entry in feed.entries[:30]:
                    published = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published = datetime(*entry.published_parsed[:6])
                        except Exception:
                            pass

                    summary = ''
                    if hasattr(entry, 'summary'):
                        summary = re.sub(r'<[^>]+>', '', entry.summary)[:500]

                    news_item = NewsItem(
                        title=entry.get('title', ''),
                        link=entry.get('link', ''),
                        source=source,
                        published=published,
                        summary=summary,
                    )

                    self._analyze_news(news_item)
                    news_items.append(news_item)

            logger.info(f'{source}: 取得 {len(news_items)} 則新聞')
            return news_items

        except Exception as e:
            logger.error(f'抓取新聞來源失敗 ({source}): {e}')
            return []

    def _parse_json_feed(self, data: dict, source: str) -> List[NewsItem]:
        """解析 JSON API 回應 (鉅亨網格式)"""
        news_items = []

        try:
            items = data.get('items', {}).get('data', [])

            for item in items[:30]:
                published = datetime.now()
                if item.get('publishAt'):
                    try:
                        published = datetime.fromtimestamp(item['publishAt'])
                    except Exception:
                        pass

                news_item = NewsItem(
                    title=item.get('title', ''),
                    link=f"https://news.cnyes.com/news/id/{item.get('newsId', '')}",
                    source=source,
                    published=published,
                    summary=item.get('summary', '')[:500] if item.get('summary') else '',
                )

                self._analyze_news(news_item)
                news_items.append(news_item)

        except Exception as e:
            logger.error(f'解析 JSON 新聞失敗 ({source}): {e}')

        return news_items

    def fetch_all_feeds(self, feed_keys: List[str] = None) -> List[NewsItem]:
        """抓取所有 RSS Feed"""
        if feed_keys is None:
            feed_keys = list(RSS_FEEDS.keys())

        all_news = []
        seen_hashes = set()

        for feed_key in feed_keys:
            news_items = self.fetch_feed(feed_key)

            # 去重 (基於內容雜湊)
            for item in news_items:
                if item.content_hash not in seen_hashes:
                    seen_hashes.add(item.content_hash)
                    all_news.append(item)

        # 按時間排序
        all_news.sort(key=lambda x: x.published, reverse=True)
        self.news_cache = all_news

        # 建立事件群集 (用於熱門股票計算)
        self._build_event_clusters()

        # 儲存快取
        self._save_cache()

        return all_news

    def _build_event_clusters(self):
        """
        建立事件群集

        同一事件的多篇報導歸為一組，避免重複計算
        """
        self._event_clusters = defaultdict(list)

        for news in self.news_cache:
            # 使用標題前20字 + 股票組合作為事件識別
            stocks_key = ','.join(sorted(news.stocks)) if news.stocks else 'no_stock'
            title_key = re.sub(r'[\s\W]+', '', news.title[:20])
            event_key = f"{stocks_key}_{title_key}"

            self._event_clusters[event_key].append(news)

    def _save_cache(self):
        """儲存新聞快取"""
        try:
            cache_data = {
                'updated_at': datetime.now().isoformat(),
                'news': [n.to_dict() for n in self.news_cache]
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f'新聞快取已儲存: {len(self.news_cache)} 則')
        except Exception as e:
            logger.error(f'儲存新聞快取失敗: {e}')

    def load_cache(self) -> List[NewsItem]:
        """載入新聞快取"""
        if not self.cache_file.exists():
            return []

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            news_items = []
            for n in cache_data.get('news', []):
                news_items.append(NewsItem(
                    title=n['title'],
                    link=n['link'],
                    source=n['source'],
                    published=datetime.fromisoformat(n['published']),
                    summary=n.get('summary', ''),
                    stocks=n.get('stocks', []),
                    sentiment=n.get('sentiment', 'neutral'),
                    sentiment_score=n.get('sentiment_score', 0.0),
                    keywords=n.get('keywords', []),
                    content_hash=n.get('content_hash', ''),
                ))

            self.news_cache = news_items
            self._build_event_clusters()
            return news_items

        except Exception as e:
            logger.error(f'載入新聞快取失敗: {e}')
            return []

    def get_stock_news(self, stock_id: str, hours: int = 24) -> List[NewsItem]:
        """取得特定股票的相關新聞"""
        cutoff = datetime.now() - timedelta(hours=hours)

        return [
            n for n in self.news_cache
            if stock_id in n.stocks and n.published >= cutoff
        ]

    def get_positive_news(self, hours: int = 24) -> List[NewsItem]:
        """取得利多新聞"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            n for n in self.news_cache
            if n.sentiment == 'positive' and n.published >= cutoff
        ]

    def get_negative_news(self, hours: int = 24) -> List[NewsItem]:
        """取得利空新聞"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            n for n in self.news_cache
            if n.sentiment == 'negative' and n.published >= cutoff
        ]

    def get_hot_stocks(self, hours: int = 24, use_smart_ranking: bool = True) -> Dict[str, float]:
        """
        取得熱門股票

        Parameters:
        -----------
        hours : int
            時間範圍
        use_smart_ranking : bool
            是否使用智慧排名 (時間衰減、來源權重、事件去重)

        Returns:
        --------
        Dict[str, float]
            {股票代碼: 熱門分數}
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        stock_scores: Dict[str, float] = defaultdict(float)

        if use_smart_ranking:
            # 智慧排名：考慮時間衰減、來源權重、事件去重
            processed_events: Set[str] = set()

            for event_key, news_list in self._event_clusters.items():
                # 取該事件群的最新一則
                recent_news = [n for n in news_list if n.published >= cutoff]
                if not recent_news:
                    continue

                # 取權重最高的來源
                best_news = max(recent_news, key=lambda n: self._get_source_weight(n.source))

                # 計算時間衰減 (越新權重越高)
                age_hours = (datetime.now() - best_news.published).total_seconds() / 3600
                time_weight = max(0.3, 1.0 - (age_hours / hours) * 0.7)

                # 來源權重
                source_weight = self._get_source_weight(best_news.source)

                # 情緒強度加成 (有明確情緒的新聞更重要)
                sentiment_boost = 1.0 + abs(best_news.sentiment_score) * 0.3

                # 計算最終分數
                score = time_weight * source_weight * sentiment_boost

                for stock_id in best_news.stocks:
                    stock_scores[stock_id] += score

        else:
            # 簡單計數
            for news in self.news_cache:
                if news.published >= cutoff:
                    for stock_id in news.stocks:
                        stock_scores[stock_id] += 1

        # 排序
        return dict(sorted(stock_scores.items(), key=lambda x: x[1], reverse=True))

    def _get_source_weight(self, source_name: str) -> float:
        """取得來源權重"""
        for config in RSS_FEEDS.values():
            if config['name'] == source_name:
                return config.get('weight', 1.0)
        return 1.0

    def get_stock_sentiment_summary(self, stock_id: str, hours: int = 48) -> Dict:
        """
        取得股票情緒摘要

        Returns:
        --------
        Dict
            {
                'positive_count': int,
                'negative_count': int,
                'neutral_count': int,
                'avg_sentiment_score': float,
                'trend': str,  # 'bullish', 'bearish', 'neutral'
                'keywords': List[str],
            }
        """
        news_list = self.get_stock_news(stock_id, hours)

        if not news_list:
            return {
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0,
                'avg_sentiment_score': 0.0,
                'trend': 'neutral',
                'keywords': [],
            }

        positive_count = sum(1 for n in news_list if n.sentiment == 'positive')
        negative_count = sum(1 for n in news_list if n.sentiment == 'negative')
        neutral_count = sum(1 for n in news_list if n.sentiment == 'neutral')

        avg_score = sum(n.sentiment_score for n in news_list) / len(news_list)

        # 收集關鍵字
        all_keywords = []
        for n in news_list:
            all_keywords.extend(n.keywords)

        # 計算關鍵字頻率
        keyword_counts = defaultdict(int)
        for kw in all_keywords:
            keyword_counts[kw] += 1

        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        # 判斷趨勢
        if positive_count > negative_count * 1.5:
            trend = 'bullish'
        elif negative_count > positive_count * 1.5:
            trend = 'bearish'
        else:
            trend = 'neutral'

        return {
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'avg_sentiment_score': round(avg_score, 3),
            'trend': trend,
            'keywords': [kw for kw, _ in top_keywords],
        }

    def get_watchlist_news(self, stock_ids: List[str], hours: int = 48) -> List[NewsItem]:
        """取得自選股的相關新聞"""
        cutoff = datetime.now() - timedelta(hours=hours)
        result = []

        for news in self.news_cache:
            if news.published >= cutoff:
                if any(s in stock_ids for s in news.stocks):
                    result.append(news)

        return result

    def get_watchlist_alerts(self, stock_ids: List[str], hours: int = 24) -> List[Dict]:
        """
        取得自選股的重要警示

        Parameters:
        -----------
        stock_ids : List[str]
            自選股代碼列表
        hours : int
            時間範圍

        Returns:
        --------
        List[Dict]
            警示列表
        """
        alerts = []
        cutoff = datetime.now() - timedelta(hours=hours)

        for stock_id in stock_ids:
            stock_news = [n for n in self.news_cache if stock_id in n.stocks and n.published >= cutoff]

            if not stock_news:
                continue

            # 檢查是否有強烈情緒新聞
            strong_positive = [n for n in stock_news if n.sentiment == 'positive' and n.sentiment_score > 0.5]
            strong_negative = [n for n in stock_news if n.sentiment == 'negative' and n.sentiment_score < -0.5]

            if strong_negative:
                alerts.append({
                    'stock_id': stock_id,
                    'type': 'negative',
                    'level': 'warning',
                    'message': f'{stock_id} 有 {len(strong_negative)} 則利空新聞',
                    'news': strong_negative[0].title,
                    'link': strong_negative[0].link,
                })

            if strong_positive:
                alerts.append({
                    'stock_id': stock_id,
                    'type': 'positive',
                    'level': 'info',
                    'message': f'{stock_id} 有 {len(strong_positive)} 則利多新聞',
                    'news': strong_positive[0].title,
                    'link': strong_positive[0].link,
                })

            # 檢查新聞量異常
            if len(stock_news) >= 5:
                alerts.append({
                    'stock_id': stock_id,
                    'type': 'volume',
                    'level': 'info',
                    'message': f'{stock_id} 近期新聞量較多 ({len(stock_news)} 則)',
                    'news': stock_news[0].title,
                    'link': stock_news[0].link,
                })

        return alerts

    def generate_morning_report(self, refresh: bool = False) -> Dict:
        """產生每日晨報"""
        if refresh or not self.news_cache:
            self.fetch_all_feeds()

        all_positive = [n for n in self.news_cache if n.sentiment == 'positive']
        all_negative = [n for n in self.news_cache if n.sentiment == 'negative']

        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_news': len(self.news_cache),
                'positive_count': len(all_positive),
                'negative_count': len(all_negative),
                'unique_stocks': len(set(s for n in self.news_cache for s in n.stocks)),
            },
            'hot_stocks': [],
            'positive_news': [],
            'negative_news': [],
            'market_news': [],
        }

        # 熱門股票 (使用智慧排名)
        hot_stocks = self.get_hot_stocks(hours=48, use_smart_ranking=True)

        for stock_id, score in list(hot_stocks.items())[:10]:
            sentiment_summary = self.get_stock_sentiment_summary(stock_id, 48)

            report['hot_stocks'].append({
                'stock_id': stock_id,
                'score': round(score, 2),
                'mention_count': len(self.get_stock_news(stock_id, 48)),
                'positive': sentiment_summary['positive_count'],
                'negative': sentiment_summary['negative_count'],
                'trend': sentiment_summary['trend'],
                'keywords': sentiment_summary['keywords'],
            })

        # 利多新聞 (按情緒分數排序)
        sorted_positive = sorted(all_positive, key=lambda n: n.sentiment_score, reverse=True)
        for news in sorted_positive[:5]:
            report['positive_news'].append({
                'title': news.title,
                'summary': news.summary,
                'source': news.source,
                'stocks': news.stocks,
                'keywords': news.keywords,
                'link': news.link,
                'sentiment_score': round(news.sentiment_score, 2),
            })

        # 利空新聞 (按情緒分數排序)
        sorted_negative = sorted(all_negative, key=lambda n: n.sentiment_score)
        for news in sorted_negative[:5]:
            report['negative_news'].append({
                'title': news.title,
                'summary': news.summary,
                'source': news.source,
                'stocks': news.stocks,
                'keywords': news.keywords,
                'link': news.link,
                'sentiment_score': round(news.sentiment_score, 2),
            })

        # 市場要聞
        market_news = sorted(self.news_cache, key=lambda x: x.published, reverse=True)[:10]
        for news in market_news:
            report['market_news'].append({
                'title': news.title,
                'summary': news.summary,
                'source': news.source,
                'published': news.published.strftime('%H:%M'),
                'sentiment': news.sentiment,
                'sentiment_score': round(news.sentiment_score, 2),
                'link': news.link,
            })

        return report

    def get_news_trend(self, stock_id: str, days: int = 7) -> List[Dict]:
        """
        取得股票新聞趨勢 (用於圖表)

        Returns:
        --------
        List[Dict]
            [{'date': str, 'positive': int, 'negative': int, 'neutral': int, 'total': int}, ...]
        """
        cutoff = datetime.now() - timedelta(days=days)
        daily_data = defaultdict(lambda: {'positive': 0, 'negative': 0, 'neutral': 0, 'total': 0})

        for news in self.news_cache:
            if stock_id in news.stocks and news.published >= cutoff:
                date_key = news.published.strftime('%Y-%m-%d')
                daily_data[date_key][news.sentiment] += 1
                daily_data[date_key]['total'] += 1

        # 轉為列表並排序
        result = []
        for date_key in sorted(daily_data.keys()):
            result.append({
                'date': date_key,
                **daily_data[date_key]
            })

        return result


def get_news_scanner(stock_info_df=None) -> NewsScanner:
    """取得新聞掃描器實例"""
    return NewsScanner(stock_info_df)
