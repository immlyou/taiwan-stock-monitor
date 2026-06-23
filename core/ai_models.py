"""
AI 模型模組 - 使用 Claude API 進行個股智慧分析，以及 XGBoost 因子選股模型；
並提供 LSTM 趨勢預測（PyTorch 可用時）或 EWMA fallback 預測。
"""
from __future__ import annotations

import os
import logging
import numpy as np
from typing import TYPE_CHECKING, Dict, List, Optional, Any

if TYPE_CHECKING:
    from core.data_loader import DataLoader

# 嘗試載入 PyTorch（可選依賴）
try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
    logging.getLogger(__name__).info("PyTorch 可用，啟用 LSTM 深度學習預測模式")
except ImportError:
    HAS_TORCH = False
    logging.getLogger(__name__).info("PyTorch 不可用，使用 EWMA 趨勢偵測 fallback 模式")

logger = logging.getLogger(__name__)


class ClaudeStockAnalyzer:
    """使用 Claude API 進行個股智慧分析。

    採用 lazy init 設計：不在 import 時初始化 anthropic client，
    只在第一次呼叫 analyze() 時才建立，確保 graceful 降級。
    """

    _client = None
    _client_initialized = False

    # 模型名稱
    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 500

    # ── 工具函數 ────────────────────────────────────────────

    def _get_client(self):
        """Lazy init：取得 anthropic client。每次檢查 Key 是否存在。"""
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            self.__class__._client = None
            return None

        # 如果已初始化且 Key 沒變，直接回傳
        if self._client is not None:
            return self._client

        try:
            import anthropic  # noqa: PLC0415
            self.__class__._client = anthropic.Anthropic(api_key=api_key)
            logger.info("Anthropic client 初始化成功")
        except ImportError:
            logger.warning("anthropic 套件未安裝，Claude 分析功能停用")
            self.__class__._client = None

        return self.__class__._client

    # ── 資料收集 ────────────────────────────────────────────

    def _collect_data(self, stock_id: str, data_loader: "DataLoader") -> dict:
        """從 DataLoader 收集分析所需的基本面、技術面、籌碼面數據。"""
        import numpy as np
        from core.indicators import calculate_rsi, calculate_macd, calculate_sma

        result = {
            # 基本面
            "pe": None,
            "pb": None,
            "dy": None,
            "yoy": None,
            # 技術面
            "rsi": None,
            "macd": None,
            "above_ma20": None,
            # 籌碼面
            "foreign_net_5d": None,
            "foreign_direction": None,
        }

        def _latest_value(df, col_id: str):
            """從 DataFrame 取得最新非 NaN 值。"""
            try:
                if df is None:
                    return None
                if col_id in df.columns:
                    s = df[col_id].dropna()
                else:
                    s = df.dropna() if isinstance(df, __import__("pandas").Series) else None
                if s is None or len(s) == 0:
                    return None
                val = s.iloc[-1]
                return None if (isinstance(val, float) and np.isnan(val)) else val
            except Exception:
                return None

        # 基本面
        try:
            pe_df = data_loader.get("pe_ratio")
            result["pe"] = _latest_value(pe_df, stock_id)
        except Exception:
            pass

        try:
            pb_df = data_loader.get("pb_ratio")
            result["pb"] = _latest_value(pb_df, stock_id)
        except Exception:
            pass

        try:
            dy_df = data_loader.get("dividend_yield")
            result["dy"] = _latest_value(dy_df, stock_id)
        except Exception:
            pass

        try:
            yoy_df = data_loader.get("revenue_yoy")
            result["yoy"] = _latest_value(yoy_df, stock_id)
        except Exception:
            pass

        # 技術面（需要收盤價序列）
        try:
            close_df = data_loader.get("close")
            if close_df is not None and stock_id in close_df.columns:
                close_series = close_df[stock_id].dropna()

                # RSI
                if len(close_series) >= 14:
                    rsi_series = calculate_rsi(close_series, period=14)
                    if len(rsi_series) > 0:
                        result["rsi"] = round(float(rsi_series.iloc[-1]), 1)

                # MACD
                if len(close_series) >= 26:
                    macd_line, signal_line, _ = calculate_macd(close_series)
                    if len(macd_line) > 0:
                        result["macd"] = round(float(macd_line.iloc[-1]), 4)

                # 均線位置
                if len(close_series) >= 20:
                    ma20 = calculate_sma(close_series, period=20)
                    if len(ma20) > 0:
                        latest_close = float(close_series.iloc[-1])
                        latest_ma20 = float(ma20.iloc[-1])
                        result["above_ma20"] = latest_close >= latest_ma20
        except Exception as e:
            logger.debug("技術面計算失敗 %s: %s", stock_id, e)

        # 籌碼面（外資近 5 日買賣超）
        try:
            fi_df = data_loader.get("foreign_investors")
            if fi_df is not None and stock_id in fi_df.columns:
                fi_series = fi_df[stock_id].dropna().tail(5)
                if len(fi_series) > 0:
                    net_5d = float(fi_series.sum()) / 1000  # 股 -> 張
                    result["foreign_net_5d"] = round(net_5d, 0)
                    result["foreign_direction"] = "買" if net_5d >= 0 else "賣"
        except Exception:
            pass

        return result

    # ── Prompt 組合 ─────────────────────────────────────────

    def _build_prompt(self, stock_id: str, name: str, data: dict) -> str:
        """組合分析用的 prompt。"""

        def _fmt(val, unit="", decimals=1, fallback="N/A"):
            if val is None:
                return fallback
            try:
                return f"{val:.{decimals}f}{unit}"
            except Exception:
                return str(val)

        pe_str = _fmt(data["pe"])
        pb_str = _fmt(data["pb"])
        dy_str = _fmt(data["dy"], "%")
        yoy_str = _fmt(data["yoy"], "%")
        rsi_str = _fmt(data["rsi"])
        macd_str = _fmt(data["macd"], decimals=4)

        ma_pos = "N/A"
        if data["above_ma20"] is not None:
            ma_pos = "上方" if data["above_ma20"] else "下方"

        foreign_str = "N/A"
        if data["foreign_net_5d"] is not None:
            direction = data["foreign_direction"]
            shares = abs(data["foreign_net_5d"])
            foreign_str = f"{direction}超 {shares:.0f} 張"

        prompt = (
            f"你是台灣股市分析師。以下是 {stock_id} {name} 的最新數據：\n\n"
            f"基本面：PE {pe_str}, PB {pb_str}, 殖利率 {dy_str}, 營收年增率 {yoy_str}\n"
            f"技術面：RSI {rsi_str}, MACD {macd_str}, 股價在 20 日均線{ma_pos}\n"
            f"籌碼面：外資近 5 日{foreign_str}\n\n"
            "請提供：\n"
            "1. 一段話的綜合分析（繁體中文，100 字內）\n"
            "2. 投資建議：買入/持有/觀望/賣出\n"
            "3. 風險評估：低/中/高\n"
            "4. 三個關鍵因素（每個 10 字內）\n\n"
            "回應格式（請嚴格遵守）：\n"
            "分析：<一段話分析>\n"
            "建議：<買入|持有|觀望|賣出>\n"
            "風險：<低|中|高>\n"
            "因素1：<關鍵因素>\n"
            "因素2：<關鍵因素>\n"
            "因素3：<關鍵因素>"
        )
        return prompt

    # ── 回應解析 ────────────────────────────────────────────

    def _parse_response(self, text: str) -> dict:
        """解析 Claude 的文字回應為結構化 dict。"""
        lines = text.strip().splitlines()
        parsed: dict = {
            "summary": "",
            "recommendation": "觀望",
            "risk_assessment": "中",
            "key_factors": [],
        }

        key_map = {
            "分析": "summary",
            "建議": "recommendation",
            "風險": "risk_assessment",
        }

        for line in lines:
            for prefix, field in key_map.items():
                if line.startswith(f"{prefix}：") or line.startswith(f"{prefix}:"):
                    sep = "：" if "：" in line else ":"
                    value = line.split(sep, 1)[1].strip()
                    parsed[field] = value
                    break

            for i in range(1, 4):
                prefix_zh = f"因素{i}："
                prefix_en = f"因素{i}:"
                if line.startswith(prefix_zh) or line.startswith(prefix_en):
                    sep = "：" if "：" in line else ":"
                    factor = line.split(sep, 1)[1].strip()
                    parsed["key_factors"].append(factor)
                    break

        # 確保有三個關鍵因素
        while len(parsed["key_factors"]) < 3:
            parsed["key_factors"].append("")

        return parsed

    # ── 主要分析入口 ────────────────────────────────────────

    def analyze(self, stock_id: str, data_loader: "DataLoader") -> dict:
        """收集個股數據並呼叫 Claude API 進行分析。

        Parameters
        ----------
        stock_id:
            股票代號，例如 "2330"
        data_loader:
            DataLoader 實例，用於取得基本面/技術面/籌碼面數據

        Returns
        -------
        dict with keys: summary, recommendation, risk_assessment, key_factors
        若 API Key 未設定或 anthropic 未安裝，回傳帶有 error 欄位的 dict。
        """
        client = self._get_client()

        if client is None:
            return {
                "summary": "",
                "recommendation": "",
                "risk_assessment": "",
                "key_factors": [],
                "error": "ANTHROPIC_API_KEY 未設定",
            }

        # 取得股票名稱
        name = stock_id
        try:
            cats = data_loader.get("categories")
            if cats is not None:
                if "stock_id" in cats.columns and "name" in cats.columns:
                    row = cats[cats["stock_id"].astype(str) == stock_id]
                    if not row.empty:
                        name = str(row["name"].iloc[0])
                elif "name" in cats.columns:
                    if stock_id in cats.index:
                        name = str(cats.loc[stock_id, "name"])
        except Exception:
            pass

        # 收集數據
        data = self._collect_data(stock_id, data_loader)

        # 組合 prompt
        prompt = self._build_prompt(stock_id, name, data)

        # 呼叫 Claude API
        try:
            message = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text
        except Exception as e:
            logger.error("Claude API 呼叫失敗 %s: %s", stock_id, e)
            return {
                "summary": "",
                "recommendation": "",
                "risk_assessment": "",
                "key_factors": [],
                "error": f"Claude API 錯誤: {e}",
            }

        # 解析回應
        result = self._parse_response(response_text)
        return result


# ═══════════════════════════════════════════════════════════════════════════
# LSTM 趨勢預測
# ═══════════════════════════════════════════════════════════════════════════

# ─── PyTorch LSTM 網路（僅在 torch 可用時定義） ───────────────────────────

if HAS_TORCH:
    class _LSTMNet(nn.Module):
        """輕量 LSTM 網路：4 特徵輸入 → 隱藏層 32 → 輸出 5 天預測"""

        def __init__(self, input_size: int = 4, hidden_size: int = 32,
                     num_layers: int = 2, output_size: int = 5):
            super().__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=0.2,
            )
            self.fc = nn.Linear(hidden_size, output_size)

        def forward(self, x):
            h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
            c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
            out, _ = self.lstm(x, (h0, c0))
            return self.fc(out[:, -1, :])


# ─── 特徵計算工具 ──────────────────────────────────────────────────────────

def _lstm_compute_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """計算 RSI(period)，回傳與 prices 等長的陣列（前 period 個為 0.5）"""
    if len(prices) < period + 1:
        return np.full(len(prices), 0.5)

    rsi = np.full(len(prices), 0.5)
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(prices)):
        idx = i - period
        if idx > 0:
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        if avg_loss == 0:
            rsi[i] = 1.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = rs / (1.0 + rs)

    return rsi


def _lstm_compute_sma(prices: np.ndarray, period: int) -> np.ndarray:
    """簡單移動平均，頭部不足時使用累積均值"""
    sma = np.zeros(len(prices))
    for i in range(len(prices)):
        start = max(0, i - period + 1)
        sma[i] = np.mean(prices[start:i + 1])
    return sma


def _lstm_normalize(arr: np.ndarray):
    """Min-Max 正規化至 [0, 1]，回傳 (normalized, min_val, max_val)"""
    min_val = arr.min()
    max_val = arr.max()
    if max_val == min_val:
        return np.full_like(arr, 0.5, dtype=float), min_val, max_val
    return (arr - min_val) / (max_val - min_val), min_val, max_val


def _lstm_build_features(
    prices: np.ndarray,
    volumes: np.ndarray,
    lookback: int = 60,
) -> Optional[np.ndarray]:
    """
    建構 LSTM 輸入特徵矩陣，shape = (lookback, 4)

    特徵：
    - 收盤價（Min-Max 標準化）
    - 成交量（Min-Max 標準化）
    - RSI(14)（已在 0–1 範圍）
    - 5日均線 / 20日均線 比值（clamp 至 [0.5, 2.0]，再線性縮放至 [0, 1]）
    """
    if len(prices) < lookback:
        return None

    price_window = prices[-lookback:]
    if len(volumes) >= lookback:
        vol_window = volumes[-lookback:].astype(float)
    else:
        vol_window = np.ones(lookback)

    norm_price, _, _ = _lstm_normalize(price_window)
    norm_volume, _, _ = _lstm_normalize(vol_window)

    full_rsi = _lstm_compute_rsi(prices[-min(len(prices), lookback + 20):])
    rsi_window = full_rsi[-lookback:]

    sma5 = _lstm_compute_sma(price_window, 5)
    sma20 = _lstm_compute_sma(price_window, 20)
    with np.errstate(divide='ignore', invalid='ignore'):
        ratio = np.where(sma20 != 0, sma5 / sma20, 1.0)
    ratio = np.clip(ratio, 0.5, 2.0)
    norm_ratio = (ratio - 0.5) / 1.5

    features = np.stack([norm_price, norm_volume, rsi_window, norm_ratio], axis=1)
    return features.astype(np.float32)


def _lstm_classify_direction(change_pct: float) -> str:
    """依預測漲幅百分比判斷趨勢方向（±1.5% 為盤整閾值）"""
    if change_pct > 1.5:
        return "上漲"
    elif change_pct < -1.5:
        return "下跌"
    return "盤整"


def _lstm_trend_strength(predicted_prices: List[float], current_price: float) -> float:
    """計算趨勢強度 0.0–1.0（單調性 + 幅度綜合評分）"""
    if len(predicted_prices) < 2 or current_price == 0:
        return 0.0

    changes = [predicted_prices[i] - predicted_prices[i - 1] for i in range(1, len(predicted_prices))]
    if not changes:
        return 0.0

    dominant_sign = 1 if sum(changes) >= 0 else -1
    monotonic_ratio = sum(1 for c in changes if np.sign(c) == dominant_sign) / len(changes)

    total_change_pct = abs(predicted_prices[-1] - current_price) / current_price * 100
    amplitude_score = min(total_change_pct / 5.0, 1.0)

    return round(monotonic_ratio * 0.5 + amplitude_score * 0.5, 3)


def _lstm_confidence(
    predicted_prices: List[float],
    current_price: float,
    prices_history: np.ndarray,
    use_torch: bool,
) -> float:
    """估算預測信心度 0.0–1.0"""
    if current_price == 0:
        return 0.5

    if len(prices_history) >= 20:
        recent = prices_history[-20:]
        returns = np.diff(recent) / recent[:-1]
        volatility = float(np.std(returns))
    else:
        volatility = 0.02

    vol_score = max(0.0, 1.0 - volatility / 0.05)

    trend_score = 0.0
    if len(prices_history) >= 20:
        def _ema_last(arr, span):
            alpha = 2.0 / (span + 1)
            v = float(arr[0])
            for x in arr[1:]:
                v = alpha * float(x) + (1 - alpha) * v
            return v

        ema5 = _ema_last(prices_history[-10:], 5)
        ema20 = _ema_last(
            prices_history[-25:] if len(prices_history) >= 25 else prices_history, 20
        )
        consistent = (
            (predicted_prices[-1] > current_price and ema5 > ema20) or
            (predicted_prices[-1] < current_price and ema5 < ema20)
        )
        trend_score = 0.3 if consistent else 0.0
    else:
        trend_score = 0.15

    base = 0.55 if use_torch else 0.45
    return round(min(0.92, max(0.30, base + vol_score * 0.15 + trend_score)), 3)


# ─── PyTorch 即時訓練預測 ──────────────────────────────────────────────────

def _predict_torch(prices: np.ndarray, volumes: np.ndarray, lookback: int = 60) -> List[float]:
    """使用即時訓練的輕量 LSTM 預測未來 5 天（無預訓練權重）"""
    predict_days = 5
    current_price = float(prices[-1])

    features = _lstm_build_features(prices, volumes, lookback)
    if features is None:
        raise ValueError(f"資料不足（需 {lookback} 天，實際 {len(prices)} 天）")

    vol_data = volumes if len(volumes) == len(prices) else np.ones(len(prices))

    X_list: List[np.ndarray] = []
    y_list: List[np.ndarray] = []

    # 只建「最後會用到的」訓練樣本：模型最終只取最近 MAX_SAMPLES 筆訓練，
    # 但原本迴圈跑遍整段歷史（長個股 4000+ 天）、每次在成長中的切片重算特徵 = O(n²)，
    # 是 LSTM 端點逾時的主因。直接從尾端起算，結果相同但快得多。
    MAX_SAMPLES = 200
    loop_start = max(lookback, len(prices) - predict_days - MAX_SAMPLES)

    for i in range(loop_start, len(prices) - predict_days):
        feat = _lstm_build_features(prices[:i + 1], vol_data[:i + 1], lookback)
        if feat is None:
            continue
        win = prices[i - lookback + 1:i + 1]
        win_min, win_max = win.min(), win.max()
        future = prices[i + 1:i + 1 + predict_days]
        if win_max == win_min:
            y_list.append(np.full(predict_days, 0.5, dtype=np.float32))
        else:
            y_list.append(((future - win_min) / (win_max - win_min)).astype(np.float32))
        X_list.append(feat)

    if len(X_list) < 10:
        raise ValueError("訓練樣本不足")

    X = torch.tensor(np.array(X_list), dtype=torch.float32)
    y = torch.tensor(np.array(y_list), dtype=torch.float32)

    model = _LSTMNet(input_size=4, hidden_size=32, num_layers=2, output_size=predict_days)
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)
    criterion = nn.MSELoss()

    for _ in range(30):
        optimizer.zero_grad()
        loss = criterion(model(X), y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

    model.eval()
    with torch.no_grad():
        x_pred = torch.tensor(features[np.newaxis, :, :], dtype=torch.float32)
        pred_norm = model(x_pred).numpy()[0]

    win_min = prices[-lookback:].min()
    win_max = prices[-lookback:].max()
    raw = (pred_norm * (win_max - win_min) + win_min).tolist()

    return [
        round(max(current_price * 0.8, min(current_price * 1.2, p)), 2)
        for p in raw
    ]


# ─── EWMA fallback 預測 ────────────────────────────────────────────────────

def _predict_ewma(prices: np.ndarray, _volumes: np.ndarray) -> List[float]:
    """Fallback：指數加權移動平均 + 趨勢偵測預測未來 5 天"""
    predict_days = 5
    current_price = float(prices[-1])

    if len(prices) < 20:
        return [round(current_price * (1 + 0.001 * i), 2) for i in range(predict_days)]

    def _ema(arr, span):
        alpha = 2.0 / (span + 1)
        result = np.zeros(len(arr))
        result[0] = arr[0]
        for i in range(1, len(arr)):
            result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]
        return result

    ema5 = _ema(prices, 5)
    ema20 = _ema(prices, 20)

    window = min(5, len(ema5) - 1)
    slope5 = (ema5[-1] - ema5[-1 - window]) / (window * current_price) if current_price else 0
    slope20 = (ema20[-1] - ema20[-1 - window]) / (window * current_price) if current_price else 0
    combined_slope = slope5 * 0.7 + slope20 * 0.3

    rsi = _lstm_compute_rsi(prices[-30:] if len(prices) >= 30 else prices)
    last_rsi = float(rsi[-1])
    if last_rsi > 0.75 and combined_slope > 0:
        combined_slope *= 0.5
    elif last_rsi < 0.25 and combined_slope < 0:
        combined_slope *= 0.5

    result = []
    price = current_price
    for day in range(1, predict_days + 1):
        price = price * (1 + combined_slope * (0.9 ** day))
        price = max(current_price * 0.85, min(current_price * 1.15, price))
        result.append(round(price, 2))
    return result


# ─── 主類別 ────────────────────────────────────────────────────────────────

class LSTMTrendPredictor:
    """
    LSTM 趨勢預測 — 預測個股未來 5 日趨勢方向

    優先使用 PyTorch LSTM 即時訓練；torch 不可用時自動降級為
    EWMA（指數加權移動平均）+ 趨勢偵測 fallback。

    設計規格：
    - 單次預測 < 5 秒
    - 無需載入大型預訓練模型
    - torch 不可用時系統照常啟動

    使用範例：
        predictor = LSTMTrendPredictor()
        result = predictor.predict("2330", loader)
    """

    LOOKBACK = 60   # 歷史視窗天數
    PREDICT_DAYS = 5  # 預測天數

    def predict(self, stock_id: str, data_loader: "DataLoader") -> Dict[str, Any]:
        """
        預測個股未來 5 日趨勢。

        Parameters
        ----------
        stock_id : str
            股票代號，例如 "2330"
        data_loader : DataLoader
            DataLoader 實例

        Returns
        -------
        dict
            {
                direction: '上漲' | '下跌' | '盤整',
                confidence: float (0.0–1.0),
                predicted_prices: [{'day': 1, 'price': 850.0}, ...],
                trend_strength: float (0.0–1.0),
            }
        """
        close_df = data_loader.get("close")
        if stock_id not in close_df.columns:
            raise ValueError(f"找不到股票 {stock_id} 的收盤價資料")

        price_series = close_df[stock_id].dropna()
        if len(price_series) < 20:
            raise ValueError(
                f"股票 {stock_id} 歷史資料不足（僅 {len(price_series)} 天，需至少 20 天）"
            )

        prices = price_series.values.astype(np.float64)

        try:
            volume_df = data_loader.get("volume")
            if stock_id in volume_df.columns:
                volumes = volume_df[stock_id].reindex(price_series.index).fillna(0).values.astype(np.float64)
            else:
                volumes = np.ones(len(prices))
        except Exception:
            volumes = np.ones(len(prices))

        current_price = float(prices[-1])
        use_torch = False
        predicted_list: List[float] = []

        if HAS_TORCH and len(prices) >= self.LOOKBACK:
            try:
                predicted_list = _predict_torch(prices, volumes, self.LOOKBACK)
                use_torch = True
                logger.debug("股票 %s 使用 PyTorch LSTM 預測", stock_id)
            except Exception as e:
                logger.warning("PyTorch LSTM 失敗，降級至 EWMA: %s", e)

        if not predicted_list:
            predicted_list = _predict_ewma(prices, volumes)
            logger.debug("股票 %s 使用 EWMA fallback 預測", stock_id)

        final_price = predicted_list[-1]
        change_pct = (final_price - current_price) / current_price * 100 if current_price else 0
        direction = _lstm_classify_direction(change_pct)
        trend_strength = _lstm_trend_strength(predicted_list, current_price)
        confidence = _lstm_confidence(predicted_list, current_price, prices, use_torch)

        return {
            "direction": direction,
            "confidence": confidence,
            "predicted_prices": [
                {"day": i + 1, "price": p} for i, p in enumerate(predicted_list)
            ],
            "trend_strength": trend_strength,
        }


# ════════════════════════════════════════════════════════════════════════════
# XGBoost 因子選股模型
# ════════════════════════════════════════════════════════════════════════════

# ── XGBoost / scikit-learn 安全匯入 ─────────────────────────────────────────
try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    xgb = None
    HAS_XGBOOST = False
    logger.warning(
        "xgboost 未安裝，XGBoostStockPicker 將無法使用。"
        "請執行 pip install xgboost"
    )

try:
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    StandardScaler = None  # type: ignore[assignment,misc]
    HAS_SKLEARN = False
    logger.warning(
        "scikit-learn 未安裝，XGBoostStockPicker 將無法使用。"
        "請執行 pip install scikit-learn"
    )

import pandas as _pd  # noqa: E402

# 特徵名稱清單（與 _xgb_compute_features 欄位順序對應）
_XGBOOST_FEATURE_NAMES: List[str] = [
    "pe_ratio",
    "pb_ratio",
    "dividend_yield",
    "rsi14",
    "macd_hist",
    "sma5_pos",
    "sma20_pos",
    "volume_ratio",
    "revenue_yoy",
    "revenue_mom",
    "foreign_net_5d",
    "ret5",
    "ret20",
    "ret60",
]


# ── 工具函數 ─────────────────────────────────────────────────────────────────

def _xgb_safe_last(series: "_pd.Series") -> float:
    """取最後一個非 NaN 值；若無則回傳 NaN。"""
    dropped = series.dropna()
    return float(dropped.iloc[-1]) if len(dropped) > 0 else float("nan")


def _xgb_calc_rsi(close: "_pd.Series", period: int = 14) -> "_pd.Series":
    """計算 RSI(period)。"""
    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _xgb_calc_macd_hist(close: "_pd.Series") -> "_pd.Series":
    """計算 MACD histogram（MACD line - Signal line）。"""
    ema12  = close.ewm(span=12, adjust=False).mean()
    ema26  = close.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal


class XGBoostStockPicker:
    """XGBoost 因子選股模型 — 預測未來 20 日報酬率。

    訓練策略：
    - 使用最近 252 個交易日（約 1 年）作為訓練窗口
    - 目標變數：未來 20 交易日報酬率（前向移位計算）
    - 特徵標準化（StandardScaler）
    - XGBoost Regressor，預設 n_estimators=100, max_depth=5
    - 只在最新一日做預測，輸出 predicted_return

    記憶體優化（適合 Railway 有限記憶體環境）：
    - 每次 predict() 呼叫才訓練模型，避免常駐大型物件
    - 訓練集限 252 天，特徵矩陣規模可控
    - 過濾資料不完整的股票，降低計算量
    - 所有 NaN 填充為 0
    """

    LOOKBACK_DAYS      = 252   # 訓練窗口（約 1 年）
    FORWARD_DAYS       = 20    # 預測目標（未來 20 交易日報酬）
    MIN_VALID_FEATURES = 8     # 最新一天至少需要幾個非零特徵才納入

    def __init__(self, n_estimators: int = 100, max_depth: int = 5):
        if not HAS_XGBOOST:
            raise ImportError(
                "xgboost 未安裝，請執行 pip install xgboost 後重試。"
            )
        if not HAS_SKLEARN:
            raise ImportError(
                "scikit-learn 未安裝，請執行 pip install scikit-learn 後重試。"
            )
        self.n_estimators = n_estimators
        self.max_depth    = max_depth

    # ── 公開介面 ────────────────────────────────────────────

    def predict(self, data_loader: "DataLoader") -> List[Dict[str, Any]]:
        """執行因子選股，回傳排名後的股票清單。

        Parameters
        ----------
        data_loader : DataLoader
            已初始化的 DataLoader 實例

        Returns
        -------
        list of dict，依 predicted_return 由高到低排序。
        每筆格式：
            {
                "stock_id":               "2330",
                "predicted_return":       0.0523,
                "confidence":             0.72,
                "factors":                {"pe": 15.2, "rsi": 48.3, ...},
                "__feature_importance__": {"pe_ratio": 0.15, ...},
            }
        """
        logger.info("XGBoostStockPicker.predict() 開始執行")

        raw = self._load_data(data_loader)
        if raw is None:
            raise RuntimeError("必要資料載入失敗，無法執行模型預測")

        feature_panel, latest_features, stock_ids = self._build_feature_panel(raw)
        logger.info("有效股票數量：%d", len(stock_ids))

        if len(stock_ids) < 10:
            raise RuntimeError(
                f"有效股票不足（{len(stock_ids)} 支），無法訓練模型"
            )

        X_train, y_train, X_pred, pred_stocks = self._build_train_predict(
            feature_panel, latest_features, stock_ids, raw["close"]
        )
        logger.info(
            "訓練樣本數：%d，預測股票數：%d", len(X_train), len(pred_stocks)
        )

        model, scaler, feature_importance = self._train(X_train, y_train)
        X_pred_scaled = scaler.transform(X_pred)
        predictions   = model.predict(X_pred_scaled)

        results = self._assemble_results(
            pred_stocks, predictions, latest_features, feature_importance
        )
        logger.info("XGBoostStockPicker.predict() 完成，回傳 %d 支股票", len(results))
        return results

    # ── 私有方法 ────────────────────────────────────────────

    def _load_data(
        self, data_loader
    ) -> Optional[Dict[str, "_pd.DataFrame"]]:
        """從 DataLoader 載入所有需要的 DataFrame，只保留近期窗口節省記憶體。"""
        keys_needed = [
            "close", "pe_ratio", "pb_ratio", "dividend_yield",
            "volume", "revenue_yoy", "revenue_mom", "foreign_investors",
        ]
        raw: Dict[str, _pd.DataFrame] = {}
        needed_rows = self.LOOKBACK_DAYS + self.FORWARD_DAYS + 30

        for key in keys_needed:
            try:
                df = data_loader.get(key)
                if df is not None and len(df) > 0:
                    raw[key] = df.iloc[-needed_rows:].copy()
                else:
                    logger.warning("資料 '%s' 為空，跳過", key)
            except Exception as exc:
                logger.warning("載入 '%s' 失敗：%s", key, exc)

        if "close" not in raw:
            logger.error("無法載入收盤價資料")
            return None
        return raw

    def _build_feature_panel(
        self, raw: Dict[str, "_pd.DataFrame"]
    ):
        """為每支股票建立特徵面板。"""
        close_df = raw["close"]
        window   = self.LOOKBACK_DAYS + self.FORWARD_DAYS
        close_df = (
            close_df.iloc[-window:] if len(close_df) >= window else close_df
        )

        valid_cols = [
            c for c in close_df.columns
            if close_df[c].dropna().shape[0] >= self.LOOKBACK_DAYS
        ]

        feature_panel:   Dict[str, _pd.DataFrame] = {}
        latest_features: Dict[str, dict]          = {}

        for sid in valid_cols:
            try:
                feats, latest = self._compute_stock_features(
                    sid, close_df, raw
                )
                if feats is None:
                    continue
                feature_panel[sid]   = feats
                latest_features[sid] = latest
            except Exception as exc:
                logger.debug("股票 %s 特徵計算失敗：%s", sid, exc)

        return feature_panel, latest_features, list(feature_panel.keys())

    def _compute_stock_features(
        self,
        sid:      str,
        close_df: "_pd.DataFrame",
        raw:      Dict[str, "_pd.DataFrame"],
    ):
        """計算單一股票的所有特徵。

        Returns
        -------
        feats : pd.DataFrame 或 None（資料不足時）
        latest : dict（最新一天因子值，供前端展示）
        """
        close = close_df[sid].dropna()
        if len(close) < self.LOOKBACK_DAYS:
            return None, None

        idx = close.index

        def align(key: str) -> "_pd.Series":
            df = raw.get(key)
            if df is None or sid not in df.columns:
                return _pd.Series(np.nan, index=idx)
            return df[sid].reindex(idx, method="ffill")

        pe  = align("pe_ratio")
        pb  = align("pb_ratio")
        dy  = align("dividend_yield")

        rsi14     = _xgb_calc_rsi(close, 14)
        macd_hist = _xgb_calc_macd_hist(close)
        sma5      = close.rolling(5).mean()
        sma20     = close.rolling(20).mean()
        sma5_pos  = (close - sma5)  / sma5.replace(0, np.nan)
        sma20_pos = (close - sma20) / sma20.replace(0, np.nan)

        vol       = align("volume")
        vol_ma20  = vol.rolling(20).mean()
        vol_ratio = vol / vol_ma20.replace(0, np.nan)

        rev_yoy   = align("revenue_yoy")
        rev_mom   = align("revenue_mom")

        fi         = align("foreign_investors")
        foreign_n5 = fi.rolling(5).sum()

        ret5  = close.pct_change(5)
        ret20 = close.pct_change(20)
        ret60 = close.pct_change(60)

        feats = _pd.DataFrame(
            {
                "pe_ratio":       pe,
                "pb_ratio":       pb,
                "dividend_yield": dy,
                "rsi14":          rsi14,
                "macd_hist":      macd_hist,
                "sma5_pos":       sma5_pos,
                "sma20_pos":      sma20_pos,
                "volume_ratio":   vol_ratio,
                "revenue_yoy":    rev_yoy,
                "revenue_mom":    rev_mom,
                "foreign_net_5d": foreign_n5,
                "ret5":           ret5,
                "ret20":          ret20,
                "ret60":          ret60,
            },
            index=idx,
        )
        feats = feats.fillna(0)

        last_row = feats.iloc[-1]
        if int((last_row != 0).sum()) < self.MIN_VALID_FEATURES:
            return None, None

        latest = {
            "pe":             _xgb_safe_last(pe),
            "pb":             _xgb_safe_last(pb),
            "dividend_yield": _xgb_safe_last(dy),
            "rsi":            float(last_row["rsi14"]),
            "macd_hist":      float(last_row["macd_hist"]),
            "volume_ratio":   float(last_row["volume_ratio"]),
            "revenue_yoy":    float(last_row["revenue_yoy"]),
            "revenue_mom":    float(last_row["revenue_mom"]),
            "foreign_net_5d": float(last_row["foreign_net_5d"]),
            "ret5":           float(last_row["ret5"]),
            "ret20":          float(last_row["ret20"]),
            "ret60":          float(last_row["ret60"]),
        }
        return feats, latest

    def _build_train_predict(
        self,
        feature_panel:   Dict[str, "_pd.DataFrame"],
        latest_features: Dict[str, dict],
        stock_ids:       List[str],
        close_df:        "_pd.DataFrame",
    ):
        """組裝訓練集（歷史橫截面）和預測集（最新一天）。"""
        X_rows: List[np.ndarray] = []
        y_rows: List[np.ndarray] = []

        for sid in stock_ids:
            feats = feature_panel[sid]
            if sid not in close_df.columns:
                continue

            close   = close_df[sid].reindex(feats.index).ffill()
            fut_ret = close.pct_change(self.FORWARD_DAYS).shift(-self.FORWARD_DAYS)

            avail = len(feats) - self.FORWARD_DAYS
            if avail <= 10:
                continue

            n     = min(avail, self.LOOKBACK_DAYS)
            start = max(len(feats) - n - self.FORWARD_DAYS, 0)

            feat_slice = feats.iloc[start: start + n].values
            ret_slice  = fut_ret.iloc[start: start + n].values

            mask = ~np.isnan(ret_slice)
            if mask.sum() < 5:
                continue

            X_rows.append(feat_slice[mask])
            y_rows.append(ret_slice[mask])

        if not X_rows:
            raise RuntimeError("無法建立有效的訓練集")

        X_train = np.vstack(X_rows)
        y_train = np.concatenate(y_rows)

        X_pred_rows: List[np.ndarray] = []
        pred_stocks: List[str]         = []
        for sid in stock_ids:
            row = np.nan_to_num(feature_panel[sid].iloc[-1].values, nan=0.0)
            X_pred_rows.append(row)
            pred_stocks.append(sid)

        X_pred = np.array(X_pred_rows)
        return X_train, y_train, X_pred, pred_stocks

    def _train(self, X_train: np.ndarray, y_train: np.ndarray):
        """訓練 XGBoost 模型，回傳 (model, scaler, feature_importance)。"""
        scaler   = StandardScaler()
        X_scaled = scaler.fit_transform(X_train)

        model = xgb.XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=1,            # Railway 記憶體友善
            tree_method="hist",  # 記憶體效率最佳
            verbosity=0,
        )
        model.fit(X_scaled, y_train)

        importances = model.feature_importances_
        feature_importance = dict(
            sorted(
                {
                    name: float(round(val, 4))
                    for name, val in zip(_XGBOOST_FEATURE_NAMES, importances)
                }.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        )
        logger.info("特徵重要性 Top5: %s", list(feature_importance.items())[:5])
        return model, scaler, feature_importance

    def _assemble_results(
        self,
        pred_stocks:        List[str],
        predictions:        np.ndarray,
        latest_features:    Dict[str, dict],
        feature_importance: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """組裝最終結果，依預測報酬由高到低排序。"""
        items: List[Dict[str, Any]] = []
        pred_std = float(np.std(predictions)) if len(predictions) > 1 else 1.0

        for sid, pred in zip(pred_stocks, predictions):
            pred_val   = float(pred)
            z          = pred_val / (pred_std + 1e-9)
            confidence = float(min(1.0, max(0.0, 0.5 + z * 0.1)))

            items.append(
                {
                    "stock_id":               sid,
                    "predicted_return":       round(pred_val, 6),
                    "confidence":             round(confidence, 4),
                    "factors":                latest_features.get(sid, {}),
                    "__feature_importance__": feature_importance,
                }
            )

        items.sort(key=lambda x: x["predicted_return"], reverse=True)
        return items


# ═══════════════════════════════════════════════════════════════════════════
# Feature 2: AI 新聞情緒分析（LLM）
# ═══════════════════════════════════════════════════════════════════════════

class ClaudeNewsSentimentAnalyzer:
    """使用 Claude API 批次分析新聞情緒，取代關鍵字規則。"""

    _client = None
    MODEL = "claude-haiku-4-5-20251001"  # 用 Haiku 降低成本
    MAX_TOKENS = 1024

    def _get_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        if self._client is not None:
            return self._client
        try:
            import anthropic
            self.__class__._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            self.__class__._client = None
        return self.__class__._client

    def analyze_batch(self, news_items: List[Dict[str, str]], max_items: int = 15) -> List[Dict[str, Any]]:
        """
        批次分析新聞情緒。

        Parameters
        ----------
        news_items : list of dict
            每則新聞需有 'title' 和 'summary' 欄位
        max_items : int
            最多分析幾則（控制成本）

        Returns
        -------
        list of dict
            每則含 sentiment ('positive'/'negative'/'neutral'), score (-1~1),
            impact (str), related_stocks (list)
        """
        client = self._get_client()
        if client is None:
            return [{"error": "ANTHROPIC_API_KEY 未設定"}]

        items = news_items[:max_items]
        news_text = "\n".join(
            f"{i+1}. 標題：{n.get('title','')}\n   摘要：{n.get('summary','')[:100]}"
            for i, n in enumerate(items)
        )

        prompt = (
            "你是台灣股市新聞分析師。請分析以下新聞的市場情緒。\n\n"
            f"{news_text}\n\n"
            "請對每則新聞回傳一行，格式如下（嚴格遵守，不要多餘文字）：\n"
            "編號|情緒|分數|影響摘要|相關股票\n\n"
            "規則：\n"
            "- 情緒：positive / negative / neutral\n"
            "- 分數：-1.0 到 1.0 的浮點數\n"
            "- 影響摘要：15 字內\n"
            "- 相關股票：股票代號用逗號分隔，無則填 none\n\n"
            "範例：\n"
            "1|positive|0.7|台積電法說優於預期|2330,2303\n"
            "2|negative|-0.5|升息衝擊金融股|2882,2881"
        )

        try:
            message = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._parse_batch_response(message.content[0].text, items)
        except Exception as e:
            logger.error("新聞情緒分析失敗: %s", e)
            return [{"error": str(e)}]

    def _parse_batch_response(self, text: str, original_items: List[Dict]) -> List[Dict[str, Any]]:
        results = []
        lines = [l.strip() for l in text.strip().splitlines() if '|' in l]

        for line in lines:
            parts = line.split('|')
            if len(parts) < 5:
                continue
            try:
                idx = int(parts[0].strip()) - 1
                sentiment = parts[1].strip()
                score = float(parts[2].strip())
                impact = parts[3].strip()
                stocks_str = parts[4].strip()
                related_stocks = [s.strip() for s in stocks_str.split(',') if s.strip() != 'none'] if stocks_str else []

                original = original_items[idx] if idx < len(original_items) else {}
                results.append({
                    "title": original.get("title", ""),
                    "link": original.get("link", ""),
                    "source": original.get("source", ""),
                    "sentiment": sentiment if sentiment in ('positive', 'negative', 'neutral') else 'neutral',
                    "score": max(-1.0, min(1.0, score)),
                    "impact": impact,
                    "related_stocks": related_stocks,
                })
            except (ValueError, IndexError):
                continue

        return results


# ═══════════════════════════════════════════════════════════════════════════
# Feature 3: AI 異常偵測 + Claude 解讀
# ═══════════════════════════════════════════════════════════════════════════

class AnomalyDetector:
    """偵測股票異常訊號（爆量、跳空、法人轉向），並用 Claude 產出解讀。"""

    _client = None
    MODEL = "claude-haiku-4-5-20251001"
    MAX_TOKENS = 800

    def _get_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        if self._client is not None:
            return self._client
        try:
            import anthropic
            self.__class__._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            self.__class__._client = None
        return self.__class__._client

    def detect(self, data_loader: "DataLoader", stock_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        掃描異常訊號。

        Returns list of anomaly dicts:
            stock_id, name, anomaly_type, severity ('high'/'medium'/'low'),
            description, values (dict)
        """

        close = data_loader.get('close')
        volume = data_loader.get('volume')
        foreign = data_loader.get('foreign_investors')

        if close is None or len(close) < 5:
            return []

        if stock_ids is None:
            stock_ids = list(close.columns[:500])  # 限制掃描範圍

        anomalies = []

        for sid in stock_ids:
            if sid not in close.columns:
                continue

            prices = close[sid].dropna()
            if len(prices) < 20:
                continue

            today = float(prices.iloc[-1])
            yesterday = float(prices.iloc[-2])
            change_pct = (today / yesterday - 1) * 100 if yesterday > 0 else 0

            # 1. 爆量偵測：今日成交量 > 20 日均量 * 3
            if volume is not None and sid in volume.columns:
                vol_series = volume[sid].dropna()
                if len(vol_series) >= 20:
                    today_vol = float(vol_series.iloc[-1])
                    avg_vol_20 = float(vol_series.iloc[-20:].mean())
                    if avg_vol_20 > 0 and today_vol > avg_vol_20 * 3:
                        anomalies.append({
                            'stock_id': sid,
                            'anomaly_type': '爆量',
                            'severity': 'high' if today_vol > avg_vol_20 * 5 else 'medium',
                            'description': f'成交量為 20 日均量的 {today_vol/avg_vol_20:.1f} 倍',
                            'values': {'today_vol': today_vol, 'avg_vol_20': avg_vol_20, 'ratio': today_vol / avg_vol_20},
                        })

            # 2. 跳空偵測：開盤價與前收盤差距 > 3%
            open_df = data_loader.get('open')
            if open_df is not None and sid in open_df.columns:
                open_series = open_df[sid].dropna()
                if len(open_series) > 0:
                    today_open = float(open_series.iloc[-1])
                    gap_pct = (today_open / yesterday - 1) * 100 if yesterday > 0 else 0
                    if abs(gap_pct) > 3:
                        direction = '跳空上漲' if gap_pct > 0 else '跳空下跌'
                        anomalies.append({
                            'stock_id': sid,
                            'anomaly_type': direction,
                            'severity': 'high' if abs(gap_pct) > 5 else 'medium',
                            'description': f'開盤{"上" if gap_pct > 0 else "下"}跳 {abs(gap_pct):.1f}%',
                            'values': {'gap_pct': gap_pct, 'open': today_open, 'prev_close': yesterday},
                        })

            # 3. 法人大幅轉向：連續 5 天買超突然變賣超（或反之），且金額大
            if foreign is not None and sid in foreign.columns:
                fi = foreign[sid].dropna()
                if len(fi) >= 10:
                    recent_5 = fi.iloc[-5:].sum()
                    prev_5 = fi.iloc[-10:-5].sum()
                    if prev_5 > 0 and recent_5 < -prev_5 * 0.5:
                        anomalies.append({
                            'stock_id': sid,
                            'anomaly_type': '外資轉賣',
                            'severity': 'high',
                            'description': f'外資從近 5 日買超 {prev_5/1000:.0f} 張轉為賣超 {abs(recent_5)/1000:.0f} 張',
                            'values': {'prev_5d': prev_5, 'recent_5d': recent_5},
                        })
                    elif prev_5 < 0 and recent_5 > -prev_5 * 0.5:
                        anomalies.append({
                            'stock_id': sid,
                            'anomaly_type': '外資轉買',
                            'severity': 'medium',
                            'description': f'外資從近 5 日賣超 {abs(prev_5)/1000:.0f} 張轉為買超 {recent_5/1000:.0f} 張',
                            'values': {'prev_5d': prev_5, 'recent_5d': recent_5},
                        })

            # 4. 連續漲停/跌停
            if abs(change_pct) >= 9.5:
                prev_change = (float(prices.iloc[-2]) / float(prices.iloc[-3]) - 1) * 100 if len(prices) >= 3 else 0
                if abs(prev_change) >= 9.5 and np.sign(change_pct) == np.sign(prev_change):
                    direction = '連續漲停' if change_pct > 0 else '連續跌停'
                    anomalies.append({
                        'stock_id': sid,
                        'anomaly_type': direction,
                        'severity': 'high',
                        'description': f'連續 2 日{"漲" if change_pct > 0 else "跌"}停',
                        'values': {'today_change': change_pct, 'prev_change': prev_change},
                    })

        # 按嚴重度排序
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        anomalies.sort(key=lambda x: severity_order.get(x['severity'], 2))

        # 加入股票名稱
        try:
            stock_info = data_loader.get_stock_info()
            name_map = dict(zip(stock_info['stock_id'], stock_info['name'])) if stock_info is not None else {}
        except Exception:
            name_map = {}
        for a in anomalies:
            a['name'] = name_map.get(a['stock_id'], '')

        return anomalies

    def explain(self, anomalies: List[Dict[str, Any]], max_items: int = 10) -> str:
        """用 Claude 對偵測到的異常產出綜合解讀。"""
        client = self._get_client()
        if client is None or not anomalies:
            return ""

        items_text = "\n".join(
            f"- {a['stock_id']} {a.get('name','')}: {a['anomaly_type']} ({a['severity']}) - {a['description']}"
            for a in anomalies[:max_items]
        )

        prompt = (
            "你是台灣股市分析師。以下是今日偵測到的異常訊號：\n\n"
            f"{items_text}\n\n"
            "請提供：\n"
            "1. 整體市場解讀（50 字內）\n"
            "2. 需要特別注意的個股及原因（每檔 30 字內，最多 5 檔）\n"
            "3. 操作建議（30 字內）\n\n"
            "用繁體中文回覆，精簡扼要。"
        )

        try:
            message = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error("異常解讀失敗: %s", e)
            return f"AI 解讀失敗: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Feature 4: AI 交易日誌回顧
# ═══════════════════════════════════════════════════════════════════════════

class TradingJournalAnalyzer:
    """分析交易日誌，找出行為偏誤並產出回顧報告。"""

    _client = None
    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 1500

    def _get_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        if self._client is not None:
            return self._client
        try:
            import anthropic
            self.__class__._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            self.__class__._client = None
        return self.__class__._client

    def analyze(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析交易日誌。

        Parameters
        ----------
        entries : list of dict
            交易日誌條目（來自 trading_journal.json）

        Returns
        -------
        dict with keys: report (str), patterns (list), suggestions (list), error (str or None)
        """
        client = self._get_client()
        if client is None:
            return {"report": "", "error": "ANTHROPIC_API_KEY 未設定"}

        if not entries:
            return {"report": "尚無交易記錄可分析。", "error": None}

        # 準備交易摘要
        trade_summary = []
        for e in entries[-50:]:  # 最近 50 筆
            line = f"- {e.get('date','')} {e.get('type','')} {e.get('stock','')} "
            if e.get('price'):
                line += f"價格:{e['price']} "
            if e.get('shares'):
                line += f"股數:{e['shares']} "
            if e.get('reason'):
                line += f"原因:{e['reason'][:30]}"
            if e.get('lesson'):
                line += f" 教訓:{e['lesson'][:30]}"
            trade_summary.append(line)

        trades_text = "\n".join(trade_summary)

        # 統計
        type_counts = {}
        for e in entries:
            t = e.get('type', '其他')
            type_counts[t] = type_counts.get(t, 0) + 1

        stats = ", ".join(f"{k}:{v}次" for k, v in type_counts.items())

        prompt = (
            "你是專業的交易心理教練。請分析以下交易日誌，找出行為偏誤和改進方向。\n\n"
            f"交易統計：{stats}\n"
            f"總筆數：{len(entries)}\n\n"
            f"最近交易記錄：\n{trades_text}\n\n"
            "請提供：\n"
            "1. **交易行為分析**（100字內）：整體交易風格評估\n"
            "2. **發現的行為偏誤**（列出 2-4 個，每個 30 字內）：\n"
            "   例如：追高殺低、過度交易、停損不果斷、確認偏誤等\n"
            "3. **正面習慣**（列出 1-3 個，每個 20 字內）：做得好的地方\n"
            "4. **具體改善建議**（列出 2-3 個，每個 40 字內）\n\n"
            "用繁體中文回覆。語氣溫和但直接，像導師一樣給予建設性回饋。"
        )

        try:
            message = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return {"report": message.content[0].text, "error": None}
        except Exception as e:
            logger.error("交易日誌分析失敗: %s", e)
            return {"report": "", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# Feature 5: AI 個股對話
# ═══════════════════════════════════════════════════════════════════════════

class StockChatAssistant:
    """個股對話助手，根據股票數據上下文回答用戶問題。"""

    _client = None
    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 800

    def _get_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        if self._client is not None:
            return self._client
        try:
            import anthropic
            self.__class__._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            self.__class__._client = None
        return self.__class__._client

    def chat(self, stock_id: str, name: str, data_context: str,
             question: str, history: List[Dict[str, str]] = None) -> str:
        """
        回答關於個股的問題。

        Parameters
        ----------
        stock_id : str
        name : str
        data_context : str
            目前個股的數據摘要（價格、技術指標、基本面等）
        question : str
            用戶問題
        history : list of dict
            對話歷史 [{"role": "user"/"assistant", "content": "..."}]

        Returns
        -------
        str : AI 回覆
        """
        client = self._get_client()
        if client is None:
            return "請先設定 ANTHROPIC_API_KEY 環境變數以啟用 AI 對話功能。"

        system_prompt = (
            f"你是台灣股市分析助手。用戶正在查看 {stock_id} {name} 的分析頁面。\n"
            f"以下是該股票的最新數據：\n{data_context}\n\n"
            "規則：\n"
            "- 用繁體中文回答\n"
            "- 簡潔扼要，不超過 200 字\n"
            "- 基於數據回答，不臆測\n"
            "- 如果數據不足以回答，誠實說明\n"
            "- 投資建議需附帶風險提醒"
        )

        messages = []
        if history:
            messages.extend(history[-6:])  # 保留最近 3 輪對話
        messages.append({"role": "user", "content": question})

        try:
            message = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=system_prompt,
                messages=messages,
            )
            return message.content[0].text
        except Exception as e:
            logger.error("個股對話失敗: %s", e)
            return f"AI 回覆失敗: {e}"


# ═══════════════════════════════════════════════════════════════════════════
# Feature 6: AI 盤後摘要
# ═══════════════════════════════════════════════════════════════════════════

class PostMarketSummarizer:
    """盤後自動生成市場覆盤報告。"""

    _client = None
    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 1500

    def _get_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None
        if self._client is not None:
            return self._client
        try:
            import anthropic
            self.__class__._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            self.__class__._client = None
        return self.__class__._client

    def generate(self, market_data: Dict[str, Any]) -> Dict[str, str]:
        """
        生成盤後摘要。

        Parameters
        ----------
        market_data : dict with keys:
            date, taiex_close, taiex_change, taiex_change_pct,
            top_gainers (list), top_losers (list),
            foreign_net, trust_net, dealer_net,
            portfolio_pnl, portfolio_pnl_pct,
            notable_events (list of str)

        Returns
        -------
        dict with 'summary' (str) and 'telegram_text' (str)
        """
        client = self._get_client()
        if client is None:
            return {"summary": "", "telegram_text": "", "error": "ANTHROPIC_API_KEY 未設定"}

        # 組裝數據
        d = market_data
        gainers_text = ", ".join(
            f"{s.get('stock_id','')} {s.get('name','')}({s.get('change_pct',0):+.1f}%)"
            for s in d.get('top_gainers', [])[:5]
        )
        losers_text = ", ".join(
            f"{s.get('stock_id','')} {s.get('name','')}({s.get('change_pct',0):+.1f}%)"
            for s in d.get('top_losers', [])[:5]
        )

        prompt = (
            "你是台灣股市分析師，請根據以下數據撰寫盤後覆盤報告。\n\n"
            f"日期：{d.get('date', '')}\n"
            f"加權指數：{d.get('taiex_close', '')} ({d.get('taiex_change_pct', 0):+.2f}%)\n"
            f"三大法人：外資 {d.get('foreign_net', 0):+.0f}億 / 投信 {d.get('trust_net', 0):+.0f}億 / 自營 {d.get('dealer_net', 0):+.0f}億\n"
            f"漲幅前五：{gainers_text}\n"
            f"跌幅前五：{losers_text}\n"
        )

        if d.get('portfolio_pnl') is not None:
            prompt += f"持倉損益：{d['portfolio_pnl']:+,.0f} ({d.get('portfolio_pnl_pct', 0):+.2f}%)\n"

        if d.get('notable_events'):
            prompt += "重要事件：\n" + "\n".join(f"- {e}" for e in d['notable_events'][:5]) + "\n"

        prompt += (
            "\n請提供兩個版本：\n\n"
            "【版本A - 完整報告】（200字內）\n"
            "包含：市場概況、法人動向分析、重點個股點評、明日展望\n\n"
            "【版本B - Telegram 精簡版】（100字內）\n"
            "用 emoji 標注重點，適合手機閱讀\n\n"
            "用繁體中文。"
        )

        try:
            message = client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text

            # 拆分兩個版本
            summary = text
            telegram_text = text

            if '版本A' in text and '版本B' in text:
                parts = text.split('版本B')
                summary = parts[0].replace('【版本A - 完整報告】', '').replace('【版本A', '').strip().strip('】').strip()
                telegram_text = parts[1].replace(' - Telegram 精簡版】', '').replace('】', '').strip()
            elif '版本B' in text:
                parts = text.split('版本B')
                summary = parts[0].strip()
                telegram_text = parts[1].strip()

            # 清理前綴
            for prefix in ['【', '- 完整報告】', '- Telegram 精簡版】']:
                summary = summary.replace(prefix, '')
                telegram_text = telegram_text.replace(prefix, '')

            return {"summary": summary.strip(), "telegram_text": telegram_text.strip(), "error": None}
        except Exception as e:
            logger.error("盤後摘要生成失敗: %s", e)
            return {"summary": "", "telegram_text": "", "error": str(e)}
