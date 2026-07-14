"""SafeJSONResponse 回歸測試：原生 Python NaN/Inf 必須被清成 null。

背景（2026-07-15 健檢 P0）：原本 render() 用
``json.dumps(content, allow_nan=False, default=self._default)``，但 encoder 對
原生 float 直接處理，``allow_nan=False`` 會在呼叫 default 之前就對 NaN/Inf 拋
ValueError → 全站預設回應類別在遇到原生 NaN/Inf 時會炸成裸 500。修法是改成
「先遞迴 sanitize 再 dumps」。本測試鎖住此行為，避免回歸。
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from api.response import SafeJSONResponse, _sanitize


def _render(content):
    """跑實際 render 路徑並解析回 Python 物件。"""
    return json.loads(SafeJSONResponse(content).render(content).decode("utf-8"))


class TestSafeJSONResponseNativeFloats:
    def test_native_inf_becomes_null(self):
        # 修復前：這行會拋 ValueError（Out of range float values are not JSON compliant）
        assert _render({"a": float("inf")}) == {"a": None}

    def test_native_negative_inf_becomes_null(self):
        assert _render({"a": float("-inf")}) == {"a": None}

    def test_native_nan_becomes_null(self):
        assert _render({"a": float("nan")}) == {"a": None}

    def test_nested_and_mixed_native_floats(self):
        content = {
            "top_gainers": [
                {"stock_id": "0000", "change_pct": float("inf")},
                {"stock_id": "1111", "change_pct": 3.14},
            ],
            "nested": {"deep": [float("nan"), 1.0, float("-inf")]},
            "ok": 42,
        }
        assert _render(content) == {
            "top_gainers": [
                {"stock_id": "0000", "change_pct": None},
                {"stock_id": "1111", "change_pct": 3.14},
            ],
            "nested": {"deep": [None, 1.0, None]},
            "ok": 42,
        }

    def test_finite_native_float_preserved(self):
        assert _render({"pct": round(2.005, 2)}) == {"pct": 2.0}


class TestSafeJSONResponseNumpy:
    def test_numpy_nan_becomes_null(self):
        assert _render({"a": np.float64("nan")}) == {"a": None}

    def test_numpy_inf_becomes_null(self):
        assert _render({"a": np.float64("inf")}) == {"a": None}

    def test_numpy_int_preserved(self):
        assert _render({"a": np.int64(7)}) == {"a": 7}

    def test_numpy_array_serialized(self):
        assert _render({"a": np.array([1.0, float("inf"), 3.0])}) == {
            "a": [1.0, None, 3.0]
        }


class TestSanitizeUnit:
    def test_sanitize_handles_tuple(self):
        assert _sanitize((float("inf"), 2)) == [None, 2]

    def test_sanitize_passthrough_str_and_bool(self):
        assert _sanitize({"s": "x", "b": True, "n": None}) == {
            "s": "x",
            "b": True,
            "n": None,
        }

    def test_no_valueerror_on_render(self):
        # 直接證明修復前的失敗路徑不再發生
        try:
            SafeJSONResponse({"v": float("inf")}).render({"v": float("inf")})
        except ValueError as exc:  # pragma: no cover
            pytest.fail(f"render() 不應對原生 Inf 拋 ValueError: {exc}")
