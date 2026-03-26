"""
Dcard 股票版掃描模組 - 台股討論分析
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
class DcardPost:
    """Dcard 貼文"""
    id: int
    title: str
    excerpt: str
    created_at: datetime
    like_count: int = 0
    comment_count: int = 0
    url: str = ''
    stocks: List[str] = field(default_factory=list)
    sentiment: str = 'neutral'


class DcardScanner:
    """
    Dcard 股票版掃描器
    透過網頁抓取討論
    """

    # Dcard 股票版網頁
    FORUM_URL = 'https://www.dcard.tw/f/stock'
    POST_URL = 'https://www.dcard.tw/f/stock/p/'

    def __init__(self):
        self.posts_cache: List[DcardPost] = []
        self.cache_file = Path(__file__).parent.parent / 'data' / 'dcard_cache.json'

        # 股票代碼正則表達式
        self.stock_pattern = re.compile(r'\b(\d{4})\b')

        # 情緒關鍵字
        self.positive_keywords = [
            '多', '買', '漲', '噴', '飆', '衝', '強', '讚',
            '利多', '看好', '加碼', '進場', '起飛', '突破', '創高',
            '主力買', '外資買', '投信買', '紅K', '長紅', '賺',
        ]
        self.negative_keywords = [
            '空', '賣', '跌', '崩', '殺', '弱', '慘', '虧',
            '利空', '看壞', '減碼', '出場', '套牢', '跌破', '創低',
            '主力賣', '外資賣', '投信賣', '黑K', '長黑', '賠',
        ]

        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        # 嘗試使用 cloudscraper 繞過反爬蟲
        try:
            import cloudscraper
            self.scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'darwin',
                    'mobile': False
                }
            )
        except ImportError:
            self.scraper = None

        # 檢查 Playwright 是否可用
        self.playwright_available = False
        try:
            from playwright.sync_api import sync_playwright
            self.playwright_available = True
        except ImportError:
            pass

    def fetch_posts(self, limit: int = 100) -> List[DcardPost]:
        """
        抓取 Dcard 股票版文章 (透過 Google Cache 或備用 API)

        Parameters:
        -----------
        limit : int
            抓取文章數量

        Returns:
        --------
        List[DcardPost]
            文章列表
        """
        all_posts = []

        # 嘗試使用備用 API endpoint
        api_endpoints = [
            'https://www.dcard.tw/_api/forums/stock/posts?limit=30',
            'https://www.dcard.tw/service/api/v2/forums/stock/posts?limit=30',
        ]

        for api_url in api_endpoints:
            try:
                response = self.session.get(
                    api_url,
                    headers={
                        **self.headers,
                        'Accept': 'application/json',
                        'Referer': 'https://www.dcard.tw/f/stock',
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data and isinstance(data, list):
                            for item in data[:limit]:
                                created_at = datetime.now()
                                if item.get('createdAt'):
                                    try:
                                        created_at = datetime.fromisoformat(
                                            item['createdAt'].replace('Z', '+00:00')
                                        ).replace(tzinfo=None)
                                    except Exception:
                                        pass

                                post = DcardPost(
                                    id=item.get('id', 0),
                                    title=item.get('title', ''),
                                    excerpt=item.get('excerpt', ''),
                                    created_at=created_at,
                                    like_count=item.get('likeCount', 0),
                                    comment_count=item.get('commentCount', 0),
                                    url=f"{self.POST_URL}{item.get('id', '')}",
                                )
                                self._analyze_post(post)
                                all_posts.append(post)

                            if all_posts:
                                logger.info(f'Dcard API 取得 {len(all_posts)} 篇文章')
                                break
                    except json.JSONDecodeError:
                        continue

            except Exception as e:
                logger.debug(f'Dcard API {api_url} 失敗: {e}')
                continue

        # 如果 API 都失敗，嘗試使用 Playwright (headless 模式)
        if not all_posts and self.playwright_available:
            logger.info('Dcard API 不可用，嘗試 Playwright headless...')
            all_posts = self._fetch_via_playwright(limit, headless=True)

        # 如果 headless 失敗且環境支援圖形介面，嘗試非 headless
        # 注意：這需要 DISPLAY 環境變數或桌面環境
        if not all_posts and self.playwright_available:
            import os
            if os.environ.get('DISPLAY') or os.name == 'nt' or 'darwin' in os.uname().sysname.lower():
                logger.info('嘗試 Playwright 非 headless 模式...')
                try:
                    all_posts = self._fetch_via_playwright(limit, headless=False)
                except Exception as e:
                    logger.debug(f'非 headless 模式失敗: {e}')

        # 如果 Playwright 也失敗，嘗試一般網頁爬蟲
        if not all_posts:
            logger.info('嘗試一般網頁爬蟲...')
            all_posts = self._fetch_via_web()

        # 更新快取
        if all_posts:
            self.posts_cache = all_posts
            self._save_cache()

        logger.info(f'Dcard 股票版共取得 {len(all_posts)} 篇文章')
        return all_posts

    def _fetch_via_playwright(self, limit: int = 50, headless: bool = True) -> List[DcardPost]:
        """使用 Playwright 真實瀏覽器抓取 Dcard"""
        posts = []

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                # 啟動瀏覽器 (可選擇是否 headless)
                # headless=False 需要圖形介面，但可以繞過部分反爬蟲
                browser = p.chromium.launch(
                    headless=headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                    ]
                )
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='zh-TW',
                )
                page = context.new_page()

                # 前往 Dcard 股票版
                logger.info('Playwright: 正在載入 Dcard 股票版...')
                page.goto(self.FORUM_URL, wait_until='domcontentloaded', timeout=30000)

                # 等待頁面載入完成
                page.wait_for_timeout(5000)

                # 等待文章列表載入 (嘗試多個選擇器)
                try:
                    page.wait_for_selector('a[href*="/p/"]', timeout=15000)
                except Exception:
                    # 如果找不到，再等一下
                    page.wait_for_timeout(3000)

                # 滾動頁面載入更多文章
                for _ in range(3):
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(1500)

                # 使用 JavaScript 直接在頁面中提取文章資料
                articles_data = page.evaluate('''
                    () => {
                        const results = [];
                        const divs = document.querySelectorAll('div');
                        const seen = new Set();

                        divs.forEach(div => {
                            const link = div.querySelector('a[href*="/f/stock/p/"]');
                            if (!link) return;

                            const href = link.getAttribute('href');
                            const match = href.match(/\\/p\\/(\\d+)/);
                            if (!match || seen.has(match[1])) return;

                            // 檢查這個 div 是否是文章卡片
                            const rect = div.getBoundingClientRect();
                            if (rect.height < 50 || rect.width < 200) return;

                            const allText = div.innerText;
                            if (allText.length < 20) return;

                            const lines = allText.split('\\n').map(l => l.trim()).filter(l => l);

                            let title = '';
                            let excerpt = '';
                            let likeCount = 0;
                            let commentCount = 0;

                            for (let i = 0; i < lines.length; i++) {
                                const line = lines[i];

                                // 跳過時間格式
                                if (/^\\d+\\s*(小時|天|分鐘|秒|月|週)/.test(line)) continue;
                                if (/^\\d{2,4}[/\\-]\\d{1,2}[/\\-]\\d{1,2}/.test(line)) continue;

                                // 提取互動數據
                                const likeMatch = line.match(/(愛心|心情)\\s*(\\d+)/);
                                if (likeMatch) {
                                    likeCount = parseInt(likeMatch[2]);
                                    continue;
                                }
                                const commentMatch = line.match(/留言\\s*(\\d+)/);
                                if (commentMatch) {
                                    commentCount = parseInt(commentMatch[2]);
                                    continue;
                                }

                                // 跳過互動數據行
                                if (/^(愛心|留言|收藏|心情)/.test(line)) continue;
                                if (/^\\d+$/.test(line)) continue;
                                if (line.length < 5) continue;
                                if (line.includes('・') && line.length < 30) continue;

                                if (!title) {
                                    title = line;
                                } else if (!excerpt && line.length > 10) {
                                    excerpt = line;
                                    break;
                                }
                            }

                            if (title && title.length >= 5) {
                                seen.add(match[1]);
                                results.push({
                                    id: parseInt(match[1]),
                                    title: title.substring(0, 100),
                                    excerpt: excerpt.substring(0, 200),
                                    url: 'https://www.dcard.tw' + href,
                                    likeCount: likeCount,
                                    commentCount: commentCount
                                });
                            }
                        });

                        return results;
                    }
                ''')

                browser.close()

            # 將 JavaScript 結果轉換為 DcardPost 物件
            for article in articles_data:
                try:
                    # 過濾掉不像文章標題的內容（如「註冊 / 登入」）
                    title = article.get('title', '')
                    if not title or '登入' in title or '註冊' in title:
                        continue

                    post = DcardPost(
                        id=article.get('id', 0),
                        title=title,
                        excerpt=article.get('excerpt', ''),
                        created_at=datetime.now(),
                        like_count=article.get('likeCount', 0),
                        comment_count=article.get('commentCount', 0),
                        url=article.get('url', ''),
                    )
                    self._analyze_post(post)
                    posts.append(post)

                    if len(posts) >= limit:
                        break

                except Exception as e:
                    logger.debug(f'解析 Dcard 文章失敗: {e}')
                    continue

            if posts:
                logger.info(f'Playwright 成功抓取 {len(posts)} 篇 Dcard 文章')

        except Exception as e:
            logger.warning(f'Playwright 抓取 Dcard 失敗: {e}')

        return posts

    def _fetch_via_web(self) -> List[DcardPost]:
        """透過 SSR 後的 HTML 解析抓取文章"""
        posts = []

        try:
            # 優先使用 cloudscraper
            if self.scraper:
                response = self.scraper.get(self.FORUM_URL, timeout=30)
            else:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                }
                response = self.session.get(self.FORUM_URL, headers=headers, timeout=30)

            if response.status_code != 200:
                logger.warning(f'Dcard 網頁請求失敗: {response.status_code}')
                return posts

            soup = BeautifulSoup(response.text, 'html.parser')

            # 方法 1: 解析 SSR 後的文章卡片元素
            # Dcard 的文章卡片通常在特定的 div 結構中
            article_cards = soup.select('article, [data-key], div[class*="PostEntry"], div[class*="post"]')

            for card in article_cards:
                try:
                    # 嘗試取得標題
                    title_elem = card.select_one('h2, h3, [class*="title"], a[href*="/p/"]')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    if not title or len(title) < 3:
                        continue

                    # 取得連結和 ID
                    link_elem = card.select_one('a[href*="/p/"]')
                    url = ''
                    post_id = 0
                    if link_elem and link_elem.get('href'):
                        href = link_elem['href']
                        url = f"https://www.dcard.tw{href}" if href.startswith('/') else href
                        # 從 URL 提取 ID
                        import re
                        id_match = re.search(r'/p/(\d+)', href)
                        if id_match:
                            post_id = int(id_match.group(1))

                    # 取得摘要
                    excerpt_elem = card.select_one('[class*="excerpt"], [class*="content"], p')
                    excerpt = excerpt_elem.get_text(strip=True)[:200] if excerpt_elem else ''

                    # 取得互動數據
                    like_count = 0
                    comment_count = 0

                    # 嘗試找愛心數
                    like_elem = card.select_one('[class*="like"], [class*="heart"]')
                    if like_elem:
                        like_text = like_elem.get_text(strip=True)
                        like_match = re.search(r'(\d+)', like_text)
                        if like_match:
                            like_count = int(like_match.group(1))

                    # 嘗試找留言數
                    comment_elem = card.select_one('[class*="comment"], [class*="reply"]')
                    if comment_elem:
                        comment_text = comment_elem.get_text(strip=True)
                        comment_match = re.search(r'(\d+)', comment_text)
                        if comment_match:
                            comment_count = int(comment_match.group(1))

                    post = DcardPost(
                        id=post_id,
                        title=title,
                        excerpt=excerpt,
                        created_at=datetime.now(),
                        like_count=like_count,
                        comment_count=comment_count,
                        url=url,
                    )
                    self._analyze_post(post)
                    posts.append(post)

                except Exception as e:
                    logger.debug(f'解析 Dcard 文章卡片失敗: {e}')
                    continue

            # 方法 2: 從 Next.js 的 __NEXT_DATA__ script 中提取
            if not posts:
                next_data_script = soup.select_one('script#__NEXT_DATA__')
                if next_data_script and next_data_script.string:
                    try:
                        next_data = json.loads(next_data_script.string)
                        # 遍歷尋找文章資料
                        posts.extend(self._extract_posts_from_next_data(next_data))
                    except json.JSONDecodeError:
                        pass

            # 方法 3: 從所有 script 標籤中尋找文章資料
            if not posts:
                for script in soup.find_all('script'):
                    if script.string and 'title' in script.string and 'excerpt' in script.string:
                        try:
                            # 嘗試從 script 內容中提取 JSON
                            json_matches = re.findall(r'\{[^{}]*"title"[^{}]*\}', script.string)
                            for match in json_matches:
                                try:
                                    data = json.loads(match)
                                    if 'title' in data:
                                        post = DcardPost(
                                            id=data.get('id', 0),
                                            title=data.get('title', ''),
                                            excerpt=data.get('excerpt', ''),
                                            created_at=datetime.now(),
                                            like_count=data.get('likeCount', 0),
                                            comment_count=data.get('commentCount', 0),
                                        )
                                        self._analyze_post(post)
                                        posts.append(post)
                                except json.JSONDecodeError:
                                    continue
                        except Exception:
                            continue

            if posts:
                logger.info(f'從 Dcard SSR HTML 解析取得 {len(posts)} 篇文章')

        except Exception as e:
            logger.warning(f'Dcard 網頁爬蟲失敗: {e}')

        return posts

    def _extract_posts_from_next_data(self, data: dict, posts: List[DcardPost] = None) -> List[DcardPost]:
        """遞迴從 Next.js __NEXT_DATA__ 中提取文章"""
        if posts is None:
            posts = []

        if isinstance(data, dict):
            # 檢查是否是文章物件
            if 'title' in data and ('excerpt' in data or 'content' in data):
                try:
                    post = DcardPost(
                        id=data.get('id', 0),
                        title=data.get('title', ''),
                        excerpt=data.get('excerpt', data.get('content', ''))[:200],
                        created_at=datetime.now(),
                        like_count=data.get('likeCount', 0),
                        comment_count=data.get('commentCount', 0),
                        url=f"{self.POST_URL}{data.get('id', '')}" if data.get('id') else '',
                    )
                    self._analyze_post(post)
                    posts.append(post)
                except Exception:
                    pass

            # 遞迴搜尋
            for value in data.values():
                self._extract_posts_from_next_data(value, posts)

        elif isinstance(data, list):
            for item in data:
                self._extract_posts_from_next_data(item, posts)

        return posts

    def is_available(self) -> bool:
        """檢查 Dcard API 是否可用"""
        try:
            response = self.session.get(
                'https://www.dcard.tw/_api/forums/stock/posts?limit=1',
                headers={**self.headers, 'Accept': 'application/json'},
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

    def _analyze_post(self, post: DcardPost):
        """分析貼文內容"""
        text = post.title + ' ' + post.excerpt

        # 提取股票代碼
        stocks = self.stock_pattern.findall(text)
        valid_stocks = [s for s in stocks if 1000 <= int(s) <= 9999]
        post.stocks = list(set(valid_stocks))

        # 情緒分析
        positive_count = sum(1 for kw in self.positive_keywords if kw in text)
        negative_count = sum(1 for kw in self.negative_keywords if kw in text)

        # 也考慮按讚數
        if post.like_count >= 50:
            positive_count += 1

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
                        'id': p.id,
                        'title': p.title,
                        'excerpt': p.excerpt,
                        'created_at': p.created_at.isoformat(),
                        'like_count': p.like_count,
                        'comment_count': p.comment_count,
                        'url': p.url,
                        'stocks': p.stocks,
                        'sentiment': p.sentiment,
                    }
                    for p in self.posts_cache
                ]
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.info(f'Dcard 快取已儲存: {len(self.posts_cache)} 篇')
        except Exception as e:
            logger.error(f'儲存 Dcard 快取失敗: {e}')

    def load_cache(self) -> List[DcardPost]:
        """載入快取"""
        if not self.cache_file.exists():
            return []

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            posts = []
            for p in cache_data.get('posts', []):
                posts.append(DcardPost(
                    id=p['id'],
                    title=p['title'],
                    excerpt=p.get('excerpt', ''),
                    created_at=datetime.fromisoformat(p['created_at']),
                    like_count=p.get('like_count', 0),
                    comment_count=p.get('comment_count', 0),
                    url=p.get('url', ''),
                    stocks=p.get('stocks', []),
                    sentiment=p.get('sentiment', 'neutral'),
                ))

            self.posts_cache = posts
            logger.info(f'Dcard 快取已載入: {len(posts)} 篇')
            return posts

        except Exception as e:
            logger.error(f'載入 Dcard 快取失敗: {e}')
            return []


# 測試用
if __name__ == '__main__':
    scanner = DcardScanner()
    posts = scanner.fetch_posts(limit=30)
    print(f'取得 {len(posts)} 篇文章')
    for p in posts[:5]:
        print(f'[{p.sentiment}] {p.title[:40]}... (讚:{p.like_count})')
        if p.stocks:
            print(f'  股票: {p.stocks}')
