"""
技術指標模組 - 提供各種技術與基本面指標計算
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict


# ============== 時間框架重採樣 ==============

def resample_ohlcv(
    open_data: pd.Series,
    high_data: pd.Series,
    low_data: pd.Series,
    close_data: pd.Series,
    volume_data: Optional[pd.Series] = None,
    timeframe: str = 'W'
) -> Dict[str, pd.Series]:
    """
    將日線數據重採樣為週線或月線

    Parameters:
    -----------
    open_data : pd.Series
        開盤價序列
    high_data : pd.Series
        最高價序列
    low_data : pd.Series
        最低價序列
    close_data : pd.Series
        收盤價序列
    volume_data : pd.Series, optional
        成交量序列
    timeframe : str
        目標時間框架:
        - 'D': 日線 (不做轉換)
        - 'W': 週線
        - 'M': 月線

    Returns:
    --------
    Dict[str, pd.Series]
        包含 'open', 'high', 'low', 'close', 'volume' 的字典
    """
    if timeframe == 'D':
        result = {
            'open': open_data,
            'high': high_data,
            'low': low_data,
            'close': close_data,
        }
        if volume_data is not None:
            result['volume'] = volume_data
        return result

    # 週線或月線重採樣
    # 使用新版 pandas resample 規則: W-MON (週線以週一開始), ME (月末)
    resample_map = {
        'W': 'W-MON',  # 週線，以週一為週期起始
        'M': 'ME',     # 月線，月末 (Month End)
    }
    resample_rule = resample_map.get(timeframe, timeframe)

    result = {
        'open': open_data.resample(resample_rule).first(),
        'high': high_data.resample(resample_rule).max(),
        'low': low_data.resample(resample_rule).min(),
        'close': close_data.resample(resample_rule).last(),
    }

    if volume_data is not None:
        result['volume'] = volume_data.resample(resample_rule).sum()

    # 移除 NaN 值
    for key in result:
        result[key] = result[key].dropna()

    return result


def get_timeframe_label(timeframe: str) -> str:
    """
    取得時間框架的中文標籤

    Parameters:
    -----------
    timeframe : str
        時間框架代碼 ('D', 'W', 'M')

    Returns:
    --------
    str
        中文標籤
    """
    labels = {
        'D': '日線',
        'W': '週線',
        'M': '月線'
    }
    return labels.get(timeframe, '日線')


def get_ma_periods_for_timeframe(timeframe: str) -> Tuple[int, int, int]:
    """
    根據時間框架取得適當的均線週期

    Parameters:
    -----------
    timeframe : str
        時間框架代碼

    Returns:
    --------
    Tuple[int, int, int]
        (短期, 中期, 長期) 均線週期
    """
    periods = {
        'D': (5, 20, 60),    # 日線: 5日、20日、60日
        'W': (4, 13, 26),    # 週線: 4週、13週、26週 (約1個月、1季、半年)
        'M': (3, 6, 12),     # 月線: 3個月、6個月、12個月
    }
    return periods.get(timeframe, (5, 20, 60))


# ============== 技術指標 ==============

def sma(data: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    簡單移動平均線 (Simple Moving Average)

    Parameters:
    -----------
    data : pd.DataFrame
        價格數據
    period : int
        計算週期

    Returns:
    --------
    pd.DataFrame
        SMA 數值
    """
    return data.rolling(window=period, min_periods=1).mean()


def ema(data: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    指數移動平均線 (Exponential Moving Average)
    """
    return data.ewm(span=period, adjust=False).mean()


def rsi(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    相對強弱指標 (Relative Strength Index)

    Parameters:
    -----------
    data : pd.DataFrame
        價格數據
    period : int
        計算週期 (預設14天)

    Returns:
    --------
    pd.DataFrame
        RSI 數值 (0-100)
    """
    delta = data.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)

    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_value = 100 - (100 / (1 + rs))

    return rsi_value


def macd(data: pd.DataFrame,
         fast_period: int = 12,
         slow_period: int = 26,
         signal_period: int = 9) -> tuple:
    """
    MACD 指標

    Parameters:
    -----------
    data : pd.DataFrame
        價格數據
    fast_period : int
        快線週期
    slow_period : int
        慢線週期
    signal_period : int
        訊號線週期

    Returns:
    --------
    tuple
        (MACD線, 訊號線, 柱狀圖)
    """
    fast_ema = ema(data, fast_period)
    slow_ema = ema(data, slow_period)

    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal_period)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def bollinger_bands(data: pd.DataFrame,
                    period: int = 20,
                    std_dev: float = 2.0) -> tuple:
    """
    布林通道

    Parameters:
    -----------
    data : pd.DataFrame
        價格數據
    period : int
        計算週期
    std_dev : float
        標準差倍數

    Returns:
    --------
    tuple
        (中軌, 上軌, 下軌)
    """
    middle = sma(data, period)
    rolling_std = data.rolling(window=period, min_periods=1).std()

    upper = middle + (rolling_std * std_dev)
    lower = middle - (rolling_std * std_dev)

    return middle, upper, lower


def atr(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame,
        period: int = 14) -> pd.DataFrame:
    """
    平均真實範圍 (Average True Range)
    """
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=0).max(level=0)
    atr_value = tr.rolling(window=period, min_periods=1).mean()

    return atr_value


# ============== 價格相關指標 ==============

def returns(data: pd.DataFrame, periods: int = 1) -> pd.DataFrame:
    """計算報酬率"""
    return data.pct_change(periods=periods)


def cumulative_returns(data: pd.DataFrame) -> pd.DataFrame:
    """計算累積報酬率"""
    return (1 + returns(data)).cumprod() - 1


def drawdown(data: pd.DataFrame) -> pd.DataFrame:
    """計算回撤"""
    rolling_max = data.cummax()
    dd = (data - rolling_max) / rolling_max
    return dd


def max_drawdown(data: pd.DataFrame) -> pd.Series:
    """計算最大回撤"""
    dd = drawdown(data)
    return dd.min()


def volatility(data: pd.DataFrame, period: int = 20, annualize: bool = True) -> pd.DataFrame:
    """
    計算波動率

    Parameters:
    -----------
    data : pd.DataFrame
        價格數據
    period : int
        計算週期
    annualize : bool
        是否年化

    Returns:
    --------
    pd.DataFrame
        波動率
    """
    ret = returns(data)
    vol = ret.rolling(window=period, min_periods=1).std()

    if annualize:
        vol = vol * np.sqrt(252)  # 年化

    return vol


def highest(data: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """N日最高價"""
    return data.rolling(window=period, min_periods=1).max()


def lowest(data: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """N日最低價"""
    return data.rolling(window=period, min_periods=1).min()


def breakout_signal(data: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    突破訊號 - 當價格突破N日高點時為True
    """
    prev_highest = highest(data, period).shift(1)
    return data > prev_highest


# ============== 成交量相關指標 ==============

def volume_ratio(volume: pd.DataFrame, period: int = 5) -> pd.DataFrame:
    """
    量比 - 當日成交量 / N日平均成交量
    """
    avg_volume = sma(volume, period)
    return volume / avg_volume.replace(0, np.nan)


def obv(close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    """
    能量潮指標 (On-Balance Volume)
    """
    direction = np.sign(close.diff())
    obv_value = (volume * direction).cumsum()
    return obv_value


# ============== 基本面指標 ==============

def revenue_growth_yoy(revenue: pd.DataFrame) -> pd.DataFrame:
    """營收年增率 (需要月營收數據)"""
    return revenue.pct_change(periods=12) * 100


def revenue_growth_mom(revenue: pd.DataFrame) -> pd.DataFrame:
    """營收月增率"""
    return revenue.pct_change(periods=1) * 100


def consecutive_growth(data: pd.DataFrame, periods: int = 3) -> pd.DataFrame:
    """
    連續成長指標 - 判斷是否連續N期成長

    Returns:
    --------
    pd.DataFrame
        布林值 DataFrame，True 表示連續成長
    """
    diff = data.diff()
    is_growth = diff > 0

    # 使用滾動窗口計算連續成長期數
    result = is_growth.rolling(window=periods, min_periods=periods).sum() == periods

    return result


def rank_percentile(data: pd.DataFrame, ascending: bool = True) -> pd.DataFrame:
    """
    計算百分位排名

    Parameters:
    -----------
    data : pd.DataFrame
        數據
    ascending : bool
        True = 數值越小排名越前

    Returns:
    --------
    pd.DataFrame
        百分位排名 (0-100)
    """
    return data.rank(axis=1, ascending=ascending, pct=True) * 100


def z_score(data: pd.DataFrame, period: int = 252) -> pd.DataFrame:
    """
    計算 Z-Score (標準化分數)
    """
    mean = data.rolling(window=period, min_periods=1).mean()
    std = data.rolling(window=period, min_periods=1).std()
    return (data - mean) / std.replace(0, np.nan)


# ============== 新增技術指標 ==============

def kdj(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame,
        n: int = 9, m1: int = 3, m2: int = 3) -> tuple:
    """
    KDJ 隨機指標 (Stochastic Oscillator)

    Parameters:
    -----------
    high : pd.DataFrame
        最高價
    low : pd.DataFrame
        最低價
    close : pd.DataFrame
        收盤價
    n : int
        RSV 週期 (預設 9)
    m1 : int
        K 值平滑週期 (預設 3)
    m2 : int
        D 值平滑週期 (預設 3)

    Returns:
    --------
    tuple
        (K值, D值, J值)

    Notes:
    ------
    - K < 20 且 J < 0: 超賣區，可能反彈
    - K > 80 且 J > 100: 超買區，可能回落
    - K 上穿 D: 黃金交叉，買入訊號
    - K 下穿 D: 死亡交叉，賣出訊號
    """
    # 計算 RSV (Raw Stochastic Value)
    lowest_low = low.rolling(window=n, min_periods=1).min()
    highest_high = high.rolling(window=n, min_periods=1).max()

    rsv = (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan) * 100

    # 計算 K 值 (RSV 的 EMA)
    k = rsv.ewm(span=m1, adjust=False).mean()

    # 計算 D 值 (K 的 EMA)
    d = k.ewm(span=m2, adjust=False).mean()

    # 計算 J 值
    j = 3 * k - 2 * d

    return k, d, j


def bias(close: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    乖離率 (BIAS)

    衡量股價與移動平均線的偏離程度

    Parameters:
    -----------
    close : pd.DataFrame
        收盤價
    period : int
        移動平均週期

    Returns:
    --------
    pd.DataFrame
        乖離率 (%)

    Notes:
    ------
    - BIAS > 0: 股價高於均線，可能有回檔壓力
    - BIAS < 0: 股價低於均線，可能有反彈動能
    - 極端值通常表示超買或超賣
    """
    ma = sma(close, period)
    return ((close - ma) / ma) * 100


def williams_r(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame,
               period: int = 14) -> pd.DataFrame:
    """
    威廉指標 (Williams %R)

    衡量收盤價在過去一段時間內的相對位置

    Parameters:
    -----------
    high : pd.DataFrame
        最高價
    low : pd.DataFrame
        最低價
    close : pd.DataFrame
        收盤價
    period : int
        計算週期

    Returns:
    --------
    pd.DataFrame
        Williams %R (-100 到 0)

    Notes:
    ------
    - %R > -20: 超買區
    - %R < -80: 超賣區
    """
    highest_high = high.rolling(window=period, min_periods=1).max()
    lowest_low = low.rolling(window=period, min_periods=1).min()

    wr = (highest_high - close) / (highest_high - lowest_low).replace(0, np.nan) * -100

    return wr


def cci(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame,
        period: int = 20) -> pd.DataFrame:
    """
    商品通道指標 (Commodity Channel Index)

    Parameters:
    -----------
    high : pd.DataFrame
        最高價
    low : pd.DataFrame
        最低價
    close : pd.DataFrame
        收盤價
    period : int
        計算週期

    Returns:
    --------
    pd.DataFrame
        CCI 值

    Notes:
    ------
    - CCI > 100: 強勢行情
    - CCI < -100: 弱勢行情
    """
    # 典型價格
    tp = (high + low + close) / 3

    # 簡單移動平均
    tp_sma = tp.rolling(window=period, min_periods=1).mean()

    # 平均絕對偏差
    mad = tp.rolling(window=period, min_periods=1).apply(
        lambda x: np.abs(x - x.mean()).mean(), raw=True
    )

    cci_value = (tp - tp_sma) / (0.015 * mad).replace(0, np.nan)

    return cci_value


def adx(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame,
        period: int = 14) -> tuple:
    """
    平均方向指數 (Average Directional Index)

    衡量趨勢強度

    Parameters:
    -----------
    high : pd.DataFrame
        最高價
    low : pd.DataFrame
        最低價
    close : pd.DataFrame
        收盤價
    period : int
        計算週期

    Returns:
    --------
    tuple
        (ADX, +DI, -DI)

    Notes:
    ------
    - ADX > 25: 趨勢強勁
    - ADX < 20: 無明顯趨勢
    - +DI > -DI: 多頭趨勢
    - +DI < -DI: 空頭趨勢
    """
    # 計算 +DM 和 -DM
    high_diff = high.diff()
    low_diff = -low.diff()

    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)

    if isinstance(high, pd.DataFrame):
        plus_dm = pd.DataFrame(plus_dm, index=high.index, columns=high.columns)
        minus_dm = pd.DataFrame(minus_dm, index=high.index, columns=high.columns)
    else:
        plus_dm = pd.Series(plus_dm, index=high.index)
        minus_dm = pd.Series(minus_dm, index=high.index)

    # 計算 True Range
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=0).groupby(level=0).max() if isinstance(tr1, pd.Series) else \
         pd.DataFrame(np.maximum(np.maximum(tr1.values, tr2.values), tr3.values),
                     index=high.index, columns=high.columns)

    # 平滑處理
    atr = tr.rolling(window=period, min_periods=1).mean()
    plus_di = 100 * plus_dm.rolling(window=period, min_periods=1).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.rolling(window=period, min_periods=1).mean() / atr.replace(0, np.nan)

    # 計算 DX 和 ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_value = dx.rolling(window=period, min_periods=1).mean()

    return adx_value, plus_di, minus_di


def mfi(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame,
        volume: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    資金流量指標 (Money Flow Index)

    結合價格和成交量的動量指標

    Parameters:
    -----------
    high : pd.DataFrame
        最高價
    low : pd.DataFrame
        最低價
    close : pd.DataFrame
        收盤價
    volume : pd.DataFrame
        成交量
    period : int
        計算週期

    Returns:
    --------
    pd.DataFrame
        MFI 值 (0-100)

    Notes:
    ------
    - MFI > 80: 超買
    - MFI < 20: 超賣
    """
    # 典型價格
    tp = (high + low + close) / 3

    # 原始資金流量
    raw_mf = tp * volume

    # 正向和負向資金流量
    tp_change = tp.diff()
    positive_mf = raw_mf.where(tp_change > 0, 0)
    negative_mf = raw_mf.where(tp_change < 0, 0)

    # 計算資金流量比率
    positive_sum = positive_mf.rolling(window=period, min_periods=1).sum()
    negative_sum = negative_mf.rolling(window=period, min_periods=1).sum()

    mfr = positive_sum / negative_sum.replace(0, np.nan)

    # 計算 MFI
    mfi_value = 100 - (100 / (1 + mfr))

    return mfi_value


def psar(high: pd.DataFrame, low: pd.DataFrame,
         af_start: float = 0.02, af_step: float = 0.02, af_max: float = 0.2) -> pd.DataFrame:
    """
    拋物線轉向指標 (Parabolic SAR)

    用於判斷趨勢反轉點

    Parameters:
    -----------
    high : pd.DataFrame
        最高價
    low : pd.DataFrame
        最低價
    af_start : float
        加速因子初始值
    af_step : float
        加速因子增量
    af_max : float
        加速因子最大值

    Returns:
    --------
    pd.DataFrame
        PSAR 值

    Notes:
    ------
    - 價格 > PSAR: 多頭趨勢
    - 價格 < PSAR: 空頭趨勢
    - 價格穿越 PSAR: 趨勢反轉訊號
    """
    # 簡化實作：對每個股票分別計算
    result = pd.DataFrame(index=high.index, columns=high.columns, dtype=float)

    for col in high.columns:
        h = high[col].values
        l = low[col].values
        n = len(h)

        psar_values = np.zeros(n)
        trend = np.ones(n)  # 1 = 上漲, -1 = 下跌
        af = af_start
        ep = h[0]  # 極值點

        psar_values[0] = l[0]

        for i in range(1, n):
            if trend[i-1] == 1:  # 上漲趨勢
                psar_values[i] = psar_values[i-1] + af * (ep - psar_values[i-1])
                psar_values[i] = min(psar_values[i], l[i-1], l[i-2] if i > 1 else l[i-1])

                if l[i] < psar_values[i]:  # 反轉
                    trend[i] = -1
                    psar_values[i] = ep
                    ep = l[i]
                    af = af_start
                else:
                    trend[i] = 1
                    if h[i] > ep:
                        ep = h[i]
                        af = min(af + af_step, af_max)

            else:  # 下跌趨勢
                psar_values[i] = psar_values[i-1] + af * (ep - psar_values[i-1])
                psar_values[i] = max(psar_values[i], h[i-1], h[i-2] if i > 1 else h[i-1])

                if h[i] > psar_values[i]:  # 反轉
                    trend[i] = 1
                    psar_values[i] = ep
                    ep = h[i]
                    af = af_start
                else:
                    trend[i] = -1
                    if l[i] < ep:
                        ep = l[i]
                        af = min(af + af_step, af_max)

        result[col] = psar_values

    return result


# ============== 別名 (向後相容) ==============
# 提供 calculate_ 前綴的別名，方便其他模組導入

calculate_sma = sma
calculate_ema = ema
calculate_rsi = rsi
calculate_macd = macd
calculate_bollinger_bands = bollinger_bands
calculate_atr = atr
calculate_kdj = kdj
calculate_bias = bias
calculate_williams_r = williams_r
calculate_cci = cci
calculate_adx = adx
calculate_mfi = mfi
calculate_psar = psar
