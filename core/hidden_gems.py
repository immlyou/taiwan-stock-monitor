"""
遺珠掃描器 — 全盤掃描台股市場，找出被忽略但潛力巨大的股票

掃描 6 大面向：
1. 低估價值股（Value Hidden Gems）
2. 營收爆發但股價沒跟上（Revenue Breakout）
3. 法人悄悄布局（Institutional Stealth Buy）
4. 技術面底部反轉（Technical Reversal）
5. 小型成長股（Small Cap Growth）
6. 籌碼集中度突變（Ownership Concentration）
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from core.indicators import rsi, macd, bollinger_bands

logger = logging.getLogger(__name__)

# 每個面向最多回傳筆數
MAX_PER_CATEGORY = 15

# 綜合排名權重
WEIGHTS = {
    "value": 0.20,
    "revenue": 0.20,
    "institutional": 0.15,
    "technical": 0.15,
    "small_cap": 0.15,
    "ownership": 0.15,
}


def _safe_last(series_or_df: pd.DataFrame, col: str) -> pd.Series:
    """取 DataFrame 某一欄的最後一筆非 NaN 值（per stock）"""
    if col in series_or_df.columns:
        return series_or_df[col]
    return series_or_df.iloc[-1] if isinstance(series_or_df, pd.DataFrame) else series_or_df


def _latest_row(df: pd.DataFrame) -> pd.Series:
    """安全取得 DataFrame 最後一列"""
    if df is None or df.empty:
        return pd.Series(dtype=float)
    return df.iloc[-1]


def _last_n_rows(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """安全取得 DataFrame 最後 n 列"""
    if df is None or df.empty:
        return pd.DataFrame()
    return df.iloc[-n:]


class HiddenGemsScanner:
    """遺珠掃描器 — 全盤掃描找出被忽略的潛力股"""

    def __init__(self):
        self._name_map: Dict[str, str] = {}

    def scan(self, data_loader) -> dict:
        """
        執行全盤掃描，回傳各面向結果和綜合排名。

        Parameters
        ----------
        data_loader : DataLoader
            數據載入器實例

        Returns
        -------
        dict
            掃描結果，包含各面向 top 列表與綜合排名
        """
        # ── 載入所有需要的數據 ──
        data = self._load_data(data_loader)
        if data is None:
            return self._empty_result("數據載入失敗")

        close = data["close"]
        stocks = list(close.columns)

        # 取得股票名稱對照
        self._name_map = self._build_name_map(data_loader)

        # 排除 ETF（代號 00 開頭）
        stocks = [s for s in stocks if not s.startswith("00")]

        # 排除近 20 日均量 < 10 張的超低流動性股票
        volume = data.get("volume")
        if volume is not None:
            vol_shares = volume[stocks].iloc[-20:]
            # volume 單位是「股」，轉換成「張」= 股 / 1000
            avg_vol_lots = vol_shares.mean() / 1000
            stocks = [s for s in stocks if s in avg_vol_lots.index and avg_vol_lots.get(s, 0) >= 10]

        logger.info("遺珠掃描：共 %d 支股票（已排除 ETF 及低流動性）", len(stocks))

        # ── 建立共用指標快取 ──
        cache = self._build_cache(data, stocks)

        # ── 各面向掃描 ──
        value_gems = self._scan_value_gems(data, stocks, cache)
        revenue_breakout = self._scan_revenue_breakout(data, stocks, cache)
        stealth_buy = self._scan_stealth_buy(data, stocks, cache)
        technical_reversal = self._scan_technical_reversal(data, stocks, cache)
        small_cap_growth = self._scan_small_cap_growth(data, stocks, cache)
        ownership_shift = self._scan_ownership_shift(data, stocks, cache)

        # ── 綜合排名 ──
        composite_top20 = self._compute_composite(
            stocks, value_gems, revenue_breakout, stealth_buy,
            technical_reversal, small_cap_growth, ownership_shift,
            data, cache,
        )

        return {
            "scan_date": datetime.now().strftime("%Y-%m-%d"),
            "total_scanned": len(stocks),
            "categories": {
                "value_gems": value_gems[:MAX_PER_CATEGORY],
                "revenue_breakout": revenue_breakout[:MAX_PER_CATEGORY],
                "stealth_buy": stealth_buy[:MAX_PER_CATEGORY],
                "technical_reversal": technical_reversal[:MAX_PER_CATEGORY],
                "small_cap_growth": small_cap_growth[:MAX_PER_CATEGORY],
                "ownership_shift": ownership_shift[:MAX_PER_CATEGORY],
            },
            "composite_top20": composite_top20[:20],
        }

    # ──────────────────────────────────────────────
    # 數據載入
    # ──────────────────────────────────────────────
    def _load_data(self, loader) -> Optional[Dict[str, pd.DataFrame]]:
        """載入所有需要的 DataFrame"""
        required = ["close", "volume"]
        optional = [
            "pe_ratio", "pb_ratio", "dividend_yield",
            "revenue_yoy", "revenue_mom",
            "foreign_investors", "investment_trust",
            "foreign_holding", "margin_buy",
            "market_value",
            "inventory_over_1000_ratio",
        ]
        data: Dict[str, pd.DataFrame] = {}
        for key in required:
            try:
                data[key] = loader.get(key)
            except Exception as e:
                logger.error("載入必要數據 %s 失敗: %s", key, e)
                return None
        for key in optional:
            try:
                data[key] = loader.get(key)
            except Exception:
                logger.warning("載入選用數據 %s 失敗，跳過", key)
        return data

    def _build_name_map(self, loader) -> Dict[str, str]:
        """取得 stock_id -> name 的對照"""
        try:
            cats = loader.get("categories")
            if "stock_id" in cats.columns and "name" in cats.columns:
                return dict(zip(cats["stock_id"].astype(str), cats["name"].astype(str)))
            elif cats.index.dtype == object and "name" in cats.columns:
                return dict(zip(cats.index.astype(str), cats["name"].astype(str)))
        except Exception:
            pass
        return {}

    # ──────────────────────────────────────────────
    # 共用快取
    # ──────────────────────────────────────────────
    def _build_cache(self, data: dict, stocks: list) -> dict:
        """預先計算常用指標，避免重複計算"""
        close = data["close"][stocks]
        volume = data["volume"][stocks] if "volume" in data else None

        # 近 20 日均量（張）
        avg_vol_20 = (volume.iloc[-20:].mean() / 1000) if volume is not None else pd.Series(dtype=float)

        # 近 20 日股價漲幅
        price_now = close.iloc[-1]
        price_20d_ago = close.iloc[-20] if len(close) >= 20 else close.iloc[0]
        change_20d_pct = ((price_now - price_20d_ago) / price_20d_ago * 100).replace([np.inf, -np.inf], np.nan)

        # 近 60 日跌幅
        price_60d_ago = close.iloc[-60] if len(close) >= 60 else close.iloc[0]
        change_60d_pct = ((price_now - price_60d_ago) / price_60d_ago * 100).replace([np.inf, -np.inf], np.nan)

        # 近 60 日均量（張）
        avg_vol_60 = (volume.iloc[-60:].mean() / 1000) if volume is not None else pd.Series(dtype=float)

        return {
            "price_now": price_now,
            "avg_vol_20": avg_vol_20,
            "avg_vol_60": avg_vol_60,
            "change_20d_pct": change_20d_pct,
            "change_60d_pct": change_60d_pct,
        }

    # ──────────────────────────────────────────────
    # 1. 低估價值股
    # ──────────────────────────────────────────────
    def _scan_value_gems(self, data: dict, stocks: list, cache: dict) -> List[dict]:
        pe = data.get("pe_ratio")
        pb = data.get("pb_ratio")
        dy = data.get("dividend_yield")
        rev_yoy = data.get("revenue_yoy")

        if pe is None or pb is None or dy is None:
            return []

        pe_last = _latest_row(pe).reindex(stocks)
        pb_last = _latest_row(pb).reindex(stocks)
        dy_last = _latest_row(dy).reindex(stocks)
        rev_yoy_last = _latest_row(rev_yoy).reindex(stocks) if rev_yoy is not None else pd.Series(0, index=stocks)
        avg_vol = cache["avg_vol_20"].reindex(stocks)

        mask = (
            (pe_last > 0) & (pe_last < 12) &
            (pb_last > 0) & (pb_last < 1.0) &
            (dy_last > 5) &
            (rev_yoy_last > 0) &
            (avg_vol < 500)
        )

        candidates = [s for s in stocks if mask.get(s, False)]

        # 評分：殖利率越高越好 + PB 越低越好
        results = []
        for s in candidates:
            dy_val = dy_last.get(s, 0)
            pb_val = pb_last.get(s, 1)
            # 殖利率 0-50 分（滿分 10% 以上），PB 0-50 分（滿分 0.3 以下）
            dy_score = min(dy_val / 10 * 50, 50)
            pb_score = max(0, (1.0 - pb_val) / 0.7 * 50)
            score = dy_score + pb_score

            results.append(self._make_entry(
                s, cache, score,
                tags=["低估價值"],
                highlight=f"殖利率 {dy_val:.1f}% / PB {pb_val:.2f} / PE {pe_last.get(s, 0):.1f}",
            ))

        results.sort(key=lambda x: x["scores"]["value"], reverse=True)
        return results

    # ──────────────────────────────────────────────
    # 2. 營收爆發但股價沒跟上
    # ──────────────────────────────────────────────
    def _scan_revenue_breakout(self, data: dict, stocks: list, cache: dict) -> List[dict]:
        rev_yoy = data.get("revenue_yoy")
        rev_mom = data.get("revenue_mom")

        if rev_yoy is None or rev_mom is None:
            return []

        yoy_last = _latest_row(rev_yoy).reindex(stocks)
        mom_last = _latest_row(rev_mom).reindex(stocks)
        avg_vol = cache["avg_vol_20"].reindex(stocks)
        chg20 = cache["change_20d_pct"].reindex(stocks)

        mask = (
            (yoy_last > 30) &
            (mom_last > 10) &
            (chg20 < 5) &
            (avg_vol < 2000)
        )

        candidates = [s for s in stocks if mask.get(s, False)]

        results = []
        for s in candidates:
            yoy_val = yoy_last.get(s, 0)
            # 評分：YoY 越高越好，100% 以上滿分
            score = min(yoy_val / 100 * 100, 100)
            results.append(self._make_entry(
                s, cache, score,
                tags=["營收爆發"],
                highlight=f"營收 YoY +{yoy_val:.0f}% / MoM +{mom_last.get(s, 0):.0f}%",
                score_key="revenue",
            ))

        results.sort(key=lambda x: x["scores"]["revenue"], reverse=True)
        return results

    # ──────────────────────────────────────────────
    # 3. 法人悄悄布局
    # ──────────────────────────────────────────────
    def _scan_stealth_buy(self, data: dict, stocks: list, cache: dict) -> List[dict]:
        foreign = data.get("foreign_investors")
        trust = data.get("investment_trust")

        if foreign is None or trust is None:
            return []

        # 外資近 5 日（單位：股）
        fi_5d = _last_n_rows(foreign, 5).reindex(columns=stocks)
        it_5d = _last_n_rows(trust, 5).reindex(columns=stocks)

        # 外資連續 5 日買超
        fi_all_positive = (fi_5d > 0).all()
        # 投信 5 日淨買超 > 0
        it_net_positive = it_5d.sum() > 0

        avg_vol = cache["avg_vol_20"].reindex(stocks)
        chg20 = cache["change_20d_pct"].reindex(stocks)

        mask = fi_all_positive & it_net_positive & (avg_vol < 1000) & (chg20 < 10)

        candidates = [s for s in stocks if mask.get(s, False)]

        results = []
        for s in candidates:
            fi_sum = fi_5d[s].sum() / 1000  # 轉張
            it_sum = it_5d[s].sum() / 1000
            total = fi_sum + it_sum
            # 評分：合計買超張數越高越好，1000 張以上滿分
            score = min(abs(total) / 1000 * 100, 100)
            results.append(self._make_entry(
                s, cache, score,
                tags=["法人布局"],
                highlight=f"外資連買 5 日 +{fi_sum:.0f} 張 / 投信 +{it_sum:.0f} 張",
                score_key="institutional",
            ))

        results.sort(key=lambda x: x["scores"]["institutional"], reverse=True)
        return results

    # ──────────────────────────────────────────────
    # 4. 技術面底部反轉
    # ──────────────────────────────────────────────
    def _scan_technical_reversal(self, data: dict, stocks: list, cache: dict) -> List[dict]:
        close = data["close"][stocks]

        # RSI(14)
        rsi_df = rsi(close, 14)
        rsi_last = _latest_row(rsi_df)

        # 布林通道
        upper, middle, lower = bollinger_bands(close, 20, 2.0)
        lower_last = _latest_row(lower)
        close_last = cache["price_now"].reindex(stocks)

        # MACD histogram
        _, _, hist = macd(close)
        hist_today = _latest_row(hist)
        hist_yesterday = hist.iloc[-2] if len(hist) >= 2 else hist.iloc[-1]

        # MACD histogram 由負轉正
        macd_reversal = (hist_yesterday < 0) & (hist_today > 0)

        chg60 = cache["change_60d_pct"].reindex(stocks)

        mask = (
            (rsi_last < 35) &
            (close_last < lower_last * 1.02) &
            macd_reversal &
            (chg60 < -20)
        )

        candidates = [s for s in stocks if mask.get(s, False)]

        results = []
        for s in candidates:
            rsi_val = rsi_last.get(s, 50)
            # 評分：RSI 越低分越高
            score = max(0, (35 - rsi_val) / 35 * 100)
            results.append(self._make_entry(
                s, cache, score,
                tags=["技術反轉"],
                highlight=f"RSI {rsi_val:.0f} / 60 日跌 {chg60.get(s, 0):.0f}% / MACD 翻正",
                score_key="technical",
            ))

        results.sort(key=lambda x: x["scores"]["technical"], reverse=True)
        return results

    # ──────────────────────────────────────────────
    # 5. 小型成長股
    # ──────────────────────────────────────────────
    def _scan_small_cap_growth(self, data: dict, stocks: list, cache: dict) -> List[dict]:
        mv = data.get("market_value")
        rev_yoy = data.get("revenue_yoy")
        pe = data.get("pe_ratio")

        if mv is None or rev_yoy is None or pe is None:
            return []

        mv_last = _latest_row(mv).reindex(stocks)
        yoy_last = _latest_row(rev_yoy).reindex(stocks)
        pe_last = _latest_row(pe).reindex(stocks)
        avg_vol_60 = cache["avg_vol_60"].reindex(stocks)

        # 市值門檻：全市場中位數的 30%
        mv_valid = mv_last.dropna()
        if mv_valid.empty:
            return []
        mv_threshold = mv_valid.median() * 0.3

        mask = (
            (mv_last < mv_threshold) &
            (yoy_last > 20) &
            (pe_last > 0) & (pe_last < 20) &
            (avg_vol_60 > 50)
        )

        candidates = [s for s in stocks if mask.get(s, False)]

        results = []
        for s in candidates:
            yoy_val = yoy_last.get(s, 0)
            pe_val = pe_last.get(s, 1)
            if pe_val <= 0:
                continue
            ratio = yoy_val / pe_val
            # 評分：成長率/PE 比值越高越好，5 以上滿分
            score = min(ratio / 5 * 100, 100)
            results.append(self._make_entry(
                s, cache, score,
                tags=["小型成長"],
                highlight=f"營收 YoY +{yoy_val:.0f}% / PE {pe_val:.1f} / 成長 CP 值 {ratio:.1f}",
                score_key="small_cap",
            ))

        results.sort(key=lambda x: x["scores"]["small_cap"], reverse=True)
        return results

    # ──────────────────────────────────────────────
    # 6. 籌碼集中度突變
    # ──────────────────────────────────────────────
    def _scan_ownership_shift(self, data: dict, stocks: list, cache: dict) -> List[dict]:
        big_holder = data.get("inventory_over_1000_ratio")
        foreign_hold = data.get("foreign_holding")
        margin = data.get("margin_buy")
        volume = data.get("volume")

        if volume is None:
            return []

        vol_5d = _last_n_rows(volume, 5).reindex(columns=stocks)

        # 成交量近 5 日萎縮（今天 < 5 日均值）
        vol_shrink = vol_5d.iloc[-1] < vol_5d.mean()

        # 大戶持股比率 > 60%
        big_holder_high = pd.Series(False, index=stocks)
        big_holder_val = pd.Series(np.nan, index=stocks)
        if big_holder is not None and not big_holder.empty:
            bh_last = _latest_row(big_holder).reindex(stocks)
            big_holder_high = bh_last > 60
            big_holder_val = bh_last

        # 外資持股比率近 5 日增加 > 0.5%
        fh_increase = pd.Series(False, index=stocks)
        if foreign_hold is not None and not foreign_hold.empty:
            fh_5d = _last_n_rows(foreign_hold, 5).reindex(columns=stocks)
            if len(fh_5d) >= 2:
                fh_increase = (fh_5d.iloc[-1] - fh_5d.iloc[0]) > 0.5

        # 融資餘額近 5 日減少
        margin_decrease = pd.Series(False, index=stocks)
        if margin is not None and not margin.empty:
            mg_5d = _last_n_rows(margin, 5).reindex(columns=stocks)
            if len(mg_5d) >= 2:
                margin_decrease = mg_5d.iloc[-1] < mg_5d.iloc[0]

        # 條件：(大戶高 或 外資增) 且 融資減 且 量縮
        mask = (big_holder_high | fh_increase) & margin_decrease & vol_shrink

        candidates = [s for s in stocks if mask.get(s, False)]

        results = []
        for s in candidates:
            bh_val = big_holder_val.get(s, 0)
            score = min(bh_val / 80 * 100, 100) if bh_val > 0 and not np.isnan(bh_val) else 50
            parts = []
            if big_holder_high.get(s, False):
                parts.append(f"大戶持股 {bh_val:.0f}%")
            if fh_increase.get(s, False):
                parts.append("外資增持")
            parts.append("融資減 + 量縮")
            results.append(self._make_entry(
                s, cache, score,
                tags=["籌碼集中"],
                highlight=" / ".join(parts),
                score_key="ownership",
            ))

        results.sort(key=lambda x: x["scores"]["ownership"], reverse=True)
        return results

    # ──────────────────────────────────────────────
    # 綜合排名
    # ──────────────────────────────────────────────
    def _compute_composite(
        self, stocks, value_gems, revenue_breakout, stealth_buy,
        technical_reversal, small_cap_growth, ownership_shift,
        data, cache,
    ) -> List[dict]:
        """計算所有掃描到的股票的加權綜合分數，取 Top 20"""
        # 收集所有出現過的股票及其各面向分數
        score_map: Dict[str, Dict[str, float]] = {}
        tags_map: Dict[str, List[str]] = {}
        highlight_map: Dict[str, List[str]] = {}

        categories = [
            ("value", value_gems),
            ("revenue", revenue_breakout),
            ("institutional", stealth_buy),
            ("technical", technical_reversal),
            ("small_cap", small_cap_growth),
            ("ownership", ownership_shift),
        ]

        for key, items in categories:
            for item in items:
                sid = item["stock_id"]
                if sid not in score_map:
                    score_map[sid] = {k: 0.0 for k in WEIGHTS}
                    tags_map[sid] = []
                    highlight_map[sid] = []
                score_map[sid][key] = item["scores"].get(key, 0)
                tags_map[sid].extend(item.get("tags", []))
                if item.get("highlight"):
                    highlight_map[sid].append(item["highlight"])

        # 計算加權綜合分數
        results = []
        for sid, scores in score_map.items():
            composite = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
            scores["composite"] = round(composite, 1)

            price = cache["price_now"].get(sid, 0)
            chg = cache["change_20d_pct"].get(sid, 0)
            name = self._name_map.get(sid, "")

            # 去重 tags
            unique_tags = list(dict.fromkeys(tags_map.get(sid, [])))
            highlights = highlight_map.get(sid, [])

            results.append({
                "stock_id": sid,
                "name": name,
                "price": round(float(price), 2) if not np.isnan(price) else 0,
                "scores": {k: round(v, 1) for k, v in scores.items()},
                "tags": unique_tags,
                "highlight": " | ".join(highlights[:2]) if highlights else "",
                "change_pct": round(float(chg), 2) if not np.isnan(chg) else 0,
            })

        results.sort(key=lambda x: x["scores"]["composite"], reverse=True)
        return results

    # ──────────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────────
    def _make_entry(
        self, stock_id: str, cache: dict, score: float,
        tags: List[str], highlight: str,
        score_key: Optional[str] = None,
    ) -> dict:
        """建立單一股票的掃描結果"""
        price = cache["price_now"].get(stock_id, 0)
        chg = cache["change_20d_pct"].get(stock_id, 0)
        name = self._name_map.get(stock_id, "")

        # 決定分數放在哪個 key
        scores = {k: 0.0 for k in WEIGHTS}
        key = score_key or tags[0] if tags else "value"
        # tag -> score key mapping
        tag_to_key = {
            "低估價值": "value",
            "營收爆發": "revenue",
            "法人布局": "institutional",
            "技術反轉": "technical",
            "小型成長": "small_cap",
            "籌碼集中": "ownership",
        }
        if score_key:
            scores[score_key] = round(min(score, 100), 1)
        elif tags:
            mapped = tag_to_key.get(tags[0], "value")
            scores[mapped] = round(min(score, 100), 1)

        return {
            "stock_id": stock_id,
            "name": name,
            "price": round(float(price), 2) if not np.isnan(price) else 0,
            "scores": scores,
            "tags": tags,
            "highlight": highlight,
            "change_pct": round(float(chg), 2) if not np.isnan(chg) else 0,
        }

    def _empty_result(self, reason: str) -> dict:
        return {
            "scan_date": datetime.now().strftime("%Y-%m-%d"),
            "total_scanned": 0,
            "error": reason,
            "categories": {
                "value_gems": [],
                "revenue_breakout": [],
                "stealth_buy": [],
                "technical_reversal": [],
                "small_cap_growth": [],
                "ownership_shift": [],
            },
            "composite_top20": [],
        }
