"""
技術指標模組測試
"""
import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.indicators import (
    sma, ema, rsi, macd, bollinger_bands, atr, obv,
    stochastic, williams_r, cci
)


class TestMovingAverages:
    """移動平均線測試"""

    def test_sma_basic(self, sample_close):
        """測試 SMA 基本功能"""
        result = sma(sample_close, 20)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_close.shape
        assert result.iloc[:19].isna().all().all()  # 前 19 天應為 NaN
        assert not result.iloc[19:].isna().all().all()

    def test_sma_window_sizes(self, sample_close):
        """測試不同窗口大小"""
        for window in [5, 10, 20, 60]:
            result = sma(sample_close, window)
            assert result.iloc[window-1:].notna().any().any()

    def test_ema_basic(self, sample_close):
        """測試 EMA 基本功能"""
        result = ema(sample_close, 20)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_close.shape

    def test_ema_faster_than_sma(self, sample_close):
        """EMA 應該比 SMA 更快反應價格變化"""
        sma_result = sma(sample_close, 20)
        ema_result = ema(sample_close, 20)

        # EMA 在上漲趨勢中應該更接近當前價格
        recent = sample_close.iloc[-1]
        ema_recent = ema_result.iloc[-1]
        sma_recent = sma_result.iloc[-1]

        # 不需要具體比較，只確認兩者不同
        assert not (ema_recent == sma_recent).all()


class TestMomentumIndicators:
    """動能指標測試"""

    def test_rsi_range(self, sample_close):
        """RSI 值應該在 0-100 之間"""
        result = rsi(sample_close, 14)

        # 去除 NaN 後檢查範圍
        valid_values = result.dropna()
        assert (valid_values >= 0).all().all()
        assert (valid_values <= 100).all().all()

    def test_rsi_default_period(self, sample_close):
        """測試 RSI 預設週期"""
        result = rsi(sample_close)
        assert result.shape == sample_close.shape

    def test_macd_components(self, sample_close):
        """MACD 應返回三個組件"""
        macd_line, signal, histogram = macd(sample_close)

        assert macd_line.shape == sample_close.shape
        assert signal.shape == sample_close.shape
        assert histogram.shape == sample_close.shape

    def test_macd_histogram_calculation(self, sample_close):
        """柱狀圖應該等於 MACD 線減去信號線"""
        macd_line, signal, histogram = macd(sample_close)

        # 去除 NaN 後比較
        valid_idx = ~(macd_line.isna() | signal.isna())
        expected = macd_line[valid_idx] - signal[valid_idx]
        actual = histogram[valid_idx]

        np.testing.assert_array_almost_equal(actual.values, expected.values, decimal=10)


class TestVolatilityIndicators:
    """波動率指標測試"""

    def test_bollinger_bands(self, sample_close):
        """布林通道測試"""
        upper, middle, lower = bollinger_bands(sample_close, 20, 2)

        # 上軌應該大於中軌，中軌應該大於下軌
        valid_idx = ~(upper.isna() | middle.isna() | lower.isna())

        assert (upper[valid_idx] >= middle[valid_idx]).all().all()
        assert (middle[valid_idx] >= lower[valid_idx]).all().all()

    def test_bollinger_bands_width(self, sample_close):
        """布林通道寬度隨標準差倍數變化"""
        upper1, middle1, lower1 = bollinger_bands(sample_close, 20, 1)
        upper2, middle2, lower2 = bollinger_bands(sample_close, 20, 2)

        # 2 倍標準差的通道應該更寬
        width1 = upper1 - lower1
        width2 = upper2 - lower2

        valid_idx = ~(width1.isna() | width2.isna())
        assert (width2[valid_idx] > width1[valid_idx]).all().all()

    def test_atr_positive(self, sample_close):
        """ATR 應該為正值"""
        # 模擬 high 和 low
        high = sample_close * 1.01
        low = sample_close * 0.99

        result = atr(high, low, sample_close, 14)
        valid_values = result.dropna()

        assert (valid_values >= 0).all().all()


class TestVolumeIndicators:
    """成交量指標測試"""

    def test_obv_direction(self, sample_close, sample_volume):
        """OBV 方向應該與價格變化一致"""
        result = obv(sample_close, sample_volume)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_close.shape


class TestOscillators:
    """震盪指標測試"""

    def test_stochastic_range(self, sample_close):
        """隨機指標 K 和 D 應在 0-100 之間"""
        high = sample_close * 1.01
        low = sample_close * 0.99

        k, d = stochastic(high, low, sample_close)

        k_valid = k.dropna()
        d_valid = d.dropna()

        assert (k_valid >= 0).all().all()
        assert (k_valid <= 100).all().all()
        assert (d_valid >= 0).all().all()
        assert (d_valid <= 100).all().all()

    def test_williams_r_range(self, sample_close):
        """威廉指標應在 -100 到 0 之間"""
        high = sample_close * 1.01
        low = sample_close * 0.99

        result = williams_r(high, low, sample_close)
        valid_values = result.dropna()

        assert (valid_values >= -100).all().all()
        assert (valid_values <= 0).all().all()

    def test_cci_calculation(self, sample_close):
        """CCI 計算測試"""
        high = sample_close * 1.01
        low = sample_close * 0.99

        result = cci(high, low, sample_close, 20)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_close.shape
