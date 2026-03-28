# -*- coding: utf-8 -*-
"""
Goodinfo 資料來源模組
====================
從 goodinfo.tw 爬取個股資料，作為 FinLab 不涵蓋股票（如興櫃）的補充來源。

支援資料：
  - 即時/收盤報價（價格、成交量、漲跌幅）
  - 基本面指標（PER、PBR、殖利率）
  - 公司基本資料（產業、市場別、資本額）
  - 月營收
  - 股利政策
"""
import re
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import requests
from bs4 import BeautifulSoup

_log = logging.getLogger(__name__)

# 快取
_goodinfo_cache: Dict[str, Any] = {}
_goodinfo_cache_ts: Dict[str, float] = {}
_CACHE_TTL = 300  # 5 分鐘

# Session（重用 cookie）
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """取得或建立 requests Session"""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://goodinfo.tw/tw/",
        })
    return _session


def _parse_number(text: str, default=None) -> Optional[float]:
    """解析數字文字，處理逗號、百分比、N/A 等"""
    if not text or text.strip() in ('N/A', '-', '--', ''):
        return default
    try:
        clean = text.strip().replace(',', '').replace('%', '').replace('元', '').replace('億', '')
        return float(clean)
    except (ValueError, TypeError):
        return default


def _fetch_goodinfo_html(stock_id: str) -> Optional[str]:
    """
    取得 Goodinfo 股票詳情頁面的完整 HTML。
    處理 Goodinfo 的兩階段 cookie 驗證機制。
    """
    session = _get_session()
    base_url = f"https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={stock_id}"

    try:
        # Step 1: 取得初始頁面（JS stub），解析 CLIENT_KEY 參數
        r1 = session.get(base_url, timeout=15)
        r1.encoding = 'utf-8'

        if len(r1.text) > 5000:
            # 已經有完整頁面（cookie 有效）
            return r1.text

        # 解析 setCookie 中的常數
        m = re.search(
            r"setCookie\('CLIENT_KEY',\s*'([\d.]+)\|([\d.]+)\|([\d.]+)\|'",
            r1.text
        )
        if m:
            version, const1, const2 = m.group(1), m.group(2), m.group(3)
        else:
            # 嘗試另一種格式
            version, const1, const2 = "2.9", "37018.5", "47018.5"

        # 計算 OA date（台灣時區 UTC+8）
        tz_offset = -480  # Goodinfo 使用 -480 表示 UTC+8
        now_ms = time.time() * 1000
        oa_now = now_ms / 86400000 - tz_offset / 1440
        client_key = f"{version}|{const1}|{const2}|{tz_offset}|{oa_now}|{oa_now}"

        session.cookies.set("CLIENT_KEY", client_key, domain="goodinfo.tw", path="/")
        session.cookies.set("SCREEN_WIDTH", "1280", domain="goodinfo.tw", path="/")
        session.cookies.set("SCREEN_HEIGHT", "720", domain="goodinfo.tw", path="/")
        session.cookies.set("IS_TOUCH_DEVICE", "F", domain="goodinfo.tw", path="/")

        # Step 2: 帶 cookie 重新請求
        time.sleep(0.7)
        r2 = session.get(base_url, timeout=15)
        r2.encoding = 'utf-8'

        if len(r2.text) < 5000:
            _log.warning("[goodinfo] 無法取得完整頁面: %s (len=%d)", stock_id, len(r2.text))
            return None

        return r2.text

    except Exception as e:
        _log.error("[goodinfo] 請求失敗 (%s): %s", stock_id, e)
        return None


def fetch_stock_detail(stock_id: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    從 Goodinfo 取得個股詳細資料。

    Returns
    -------
    dict with keys:
        stock_id, name, market, industry, capital,
        price, open, high, low, prev_close, change, change_pct,
        volume_lots, turnover,
        per, pbr, peg, dividend_yield,
        market_value
    """
    cache_key = f"goodinfo_{stock_id}"

    # 檢查快取
    if use_cache and cache_key in _goodinfo_cache:
        if time.time() - _goodinfo_cache_ts.get(cache_key, 0) < _CACHE_TTL:
            return _goodinfo_cache[cache_key]

    html = _fetch_goodinfo_html(stock_id)
    if not html:
        return None

    try:
        result = _parse_stock_detail(html, stock_id)
        if result:
            _goodinfo_cache[cache_key] = result
            _goodinfo_cache_ts[cache_key] = time.time()
        return result
    except Exception as e:
        _log.error("[goodinfo] 解析失敗 (%s): %s", stock_id, e)
        return None


def _parse_stock_detail(html: str, stock_id: str) -> Optional[Dict[str, Any]]:
    """解析 Goodinfo StockDetail 頁面"""
    soup = BeautifulSoup(html, "html.parser")

    result: Dict[str, Any] = {"stock_id": stock_id}

    # ── 交易資料表 ──
    caption = soup.find("caption", string=re.compile(rf"{stock_id}.*當日及昨日交易資料"))
    if caption:
        table = caption.find_parent("table")
        if table:
            rows = table.find_all("tr")
            # 找到含有 td 的資料行（跳過 caption 和 header 行）
            data_rows = [r for r in rows if r.find_all("td") and len(r.find_all("td")) >= 6]
            if len(data_rows) >= 2:
                # 第一個資料行: 價格數據（成交價、昨收、漲跌價...）
                price_cells = data_rows[0].find_all("td")
                if len(price_cells) >= 8:
                    result["price"] = _parse_number(price_cells[0].get_text(strip=True))
                    result["prev_close"] = _parse_number(price_cells[1].get_text(strip=True))
                    result["change"] = _parse_number(price_cells[2].get_text(strip=True))
                    result["change_pct"] = _parse_number(price_cells[3].get_text(strip=True))
                    result["open"] = _parse_number(price_cells[5].get_text(strip=True))
                    result["high"] = _parse_number(price_cells[6].get_text(strip=True))
                    result["low"] = _parse_number(price_cells[7].get_text(strip=True))

                # 第二個資料行: 成交量、PBR、PER
                vol_cells = data_rows[1].find_all("td")
                if len(vol_cells) >= 6:
                    result["volume_lots"] = _parse_number(vol_cells[0].get_text(strip=True))
                    result["turnover"] = vol_cells[1].get_text(strip=True)
                    result["pbr"] = _parse_number(vol_cells[5].get_text(strip=True)) if len(vol_cells) > 5 else None
                    result["per"] = _parse_number(vol_cells[6].get_text(strip=True)) if len(vol_cells) > 6 else None
                    result["peg"] = _parse_number(vol_cells[7].get_text(strip=True)) if len(vol_cells) > 7 else None

    # ── 公司基本資料 ──
    basic_section = soup.find("section", id="secBasicInfo")
    if basic_section:
        for row in basic_section.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if not th or not td:
                continue
            label = th.get_text(strip=True)
            value = td.get_text(strip=True)

            if label == "名稱":
                result["name"] = value
            elif label == "產業別":
                result["industry"] = value
            elif label == "市場別":
                result["market"] = value  # 上市/上櫃/興櫃
            elif label == "資本額":
                result["capital"] = value
            elif label == "市值":
                result["market_value"] = value

    # ── 殖利率（從均值區取得）──
    avg_section = soup.find("div", id="divFinAvgInfo")
    if avg_section:
        for row in avg_section.find_all("tr"):
            th = row.find("th")
            if th and "現金殖利率" in th.get_text():
                tds = row.find_all("td")
                if tds:
                    result["dividend_yield"] = _parse_number(tds[0].get_text(strip=True))
                break

    # 確保至少有名稱
    if "name" not in result:
        # 從 title 取得
        title = soup.find("title")
        if title:
            m = re.search(rf"{stock_id}\s+(\S+)", title.get_text())
            if m:
                result["name"] = m.group(1)

    if "price" not in result and "name" not in result:
        return None

    return result


def fetch_ohlcv(stock_id: str, use_cache: bool = True) -> Optional[list]:
    """
    從 Goodinfo ShowK_Chart 取得每日 OHLCV 歷史資料。

    Returns
    -------
    list of dict: [{date, open, high, low, close, volume}, ...]
    按日期升序排列。
    """
    from typing import List

    cache_key = f"goodinfo_ohlcv_{stock_id}"
    if use_cache and cache_key in _goodinfo_cache:
        if time.time() - _goodinfo_cache_ts.get(cache_key, 0) < _CACHE_TTL:
            return _goodinfo_cache[cache_key]

    session = _get_session()
    url = f"https://goodinfo.tw/tw/ShowK_Chart.asp?STOCK_ID={stock_id}&CHT_CAT=DATE"

    try:
        r = session.get(url, timeout=15)
        r.encoding = "utf-8"

        if len(r.text) < 5000:
            # 需要刷新 cookie
            m = re.search(
                r"setCookie\('CLIENT_KEY',\s*'([\d.]+)\|([\d.]+)\|([\d.]+)\|'",
                r.text,
            )
            if m:
                version, c1, c2 = m.group(1), m.group(2), m.group(3)
                tz = -480
                oa = time.time() / 86400 + 25569 - tz / 1440
                session.cookies.set(
                    "CLIENT_KEY",
                    f"{version}|{c1}|{c2}|{tz}|{oa}|{oa}",
                    domain="goodinfo.tw",
                    path="/",
                )
                time.sleep(0.7)
                r = session.get(url, timeout=15)
                r.encoding = "utf-8"

        if len(r.text) < 5000:
            _log.warning("[goodinfo] OHLCV 頁面取得失敗: %s", stock_id)
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        # 找含 OHLCV 的表格（header: 交易日期, 開盤, 最高, 最低, 收盤）
        target_table = None
        for t in soup.find_all("table"):
            ths = t.find_all("th")
            header_text = " ".join(th.get_text(strip=True) for th in ths[:5])
            if "交易日期" in header_text and "開盤" in header_text and "收盤" in header_text:
                target_table = t
                break

        if not target_table:
            _log.warning("[goodinfo] 找不到 OHLCV 表格: %s", stock_id)
            return None

        records = []
        rows = target_table.find_all("tr")
        current_year = datetime.now().year

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            date_text = cells[0].get_text(strip=True)
            # 格式: '26/03/27 → 2026-03-27
            m = re.match(r"'?(\d{2})/(\d{2})/(\d{2})", date_text)
            if not m:
                continue

            yy, mm, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
            year = 2000 + yy
            date_str = f"{year}-{mm:02d}-{dd:02d}"

            open_p = _parse_number(cells[1].get_text(strip=True))
            high_p = _parse_number(cells[2].get_text(strip=True))
            low_p = _parse_number(cells[3].get_text(strip=True))
            close_p = _parse_number(cells[4].get_text(strip=True))

            # 成交量在第 8 列 (index 8) 或成交資料欄
            volume = None
            if len(cells) > 8:
                volume = _parse_number(cells[8].get_text(strip=True))

            if close_p is not None:
                records.append({
                    "date": date_str,
                    "open": open_p,
                    "high": high_p,
                    "low": low_p,
                    "close": close_p,
                    "volume": volume,
                })

        # 按日期升序
        records.sort(key=lambda x: x["date"])

        if records:
            _goodinfo_cache[cache_key] = records
            _goodinfo_cache_ts[cache_key] = time.time()

        _log.info("[goodinfo] OHLCV 成功: %s, %d 筆", stock_id, len(records))
        return records

    except Exception as e:
        _log.error("[goodinfo] OHLCV 取得失敗 (%s): %s", stock_id, e)
        return None


def fetch_monthly_revenue(stock_id: str) -> Optional[Dict[str, Any]]:
    """從 Goodinfo 取得月營收資料"""
    cache_key = f"goodinfo_rev_{stock_id}"
    if cache_key in _goodinfo_cache:
        if time.time() - _goodinfo_cache_ts.get(cache_key, 0) < _CACHE_TTL:
            return _goodinfo_cache[cache_key]

    html = _fetch_goodinfo_html(stock_id)
    if not html:
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")
        rev_div = soup.find("div", id="divSaleMonthInfo")
        if not rev_div:
            return None

        table = rev_div.find("table")
        if not table:
            return None

        revenues = []
        rows = table.find_all("tr")
        for row in rows[1:13]:  # 最近 12 個月
            cells = row.find_all("td")
            if len(cells) >= 4:
                month = cells[0].get_text(strip=True)
                rev = _parse_number(cells[1].get_text(strip=True))
                mom = _parse_number(cells[2].get_text(strip=True))
                yoy = _parse_number(cells[3].get_text(strip=True))
                if rev is not None:
                    revenues.append({
                        "month": month,
                        "revenue": rev,
                        "mom_pct": mom,
                        "yoy_pct": yoy,
                    })

        result = {"stock_id": stock_id, "revenues": revenues}
        _goodinfo_cache[cache_key] = result
        _goodinfo_cache_ts[cache_key] = time.time()
        return result

    except Exception as e:
        _log.error("[goodinfo] 營收解析失敗 (%s): %s", stock_id, e)
        return None
