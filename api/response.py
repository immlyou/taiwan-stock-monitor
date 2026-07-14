"""自訂 FastAPI JSONResponse：自動將 NaN/Infinity/numpy 型別轉為 JSON-safe"""
from __future__ import annotations

import json as _json
import math
from typing import Any

import numpy as np
from fastapi.responses import JSONResponse


def _sanitize(obj: Any) -> Any:
    """遞迴將 NaN / Infinity / numpy 型別轉為 JSON-safe 原生型別。

    必須在 json.dumps 之前執行：Python 的 JSON encoder 對原生 float 直接處理，
    ``allow_nan=False`` 時會對原生 ``float('nan')``/``float('inf')`` 直接拋
    ``ValueError``，**根本不會呼叫 default hook**（default 只在遇到未知型別時才
    觸發）。因此原生 NaN/Inf 只能靠此遞迴清洗攔下，不能依賴 default。
    """
    # 先處理 numpy（在原生 float 檢查之前，因為 np.floating 也會通過 float() 檢查）
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return [_sanitize(x) for x in obj.tolist()]
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    """自動將 NaN/Infinity 替換為 null 的 JSON Response"""

    def render(self, content: Any) -> bytes:
        # 先遞迴 sanitize 再 dumps；allow_nan=False 作為兜底（清洗漏網之魚寧可拋錯
        # 也不要產生無效 JSON），default 兜住 sanitize 未覆蓋的未知型別。
        return _json.dumps(
            _sanitize(content),
            ensure_ascii=False,
            allow_nan=False,
            default=self._default,
        ).encode("utf-8")

    @staticmethod
    def _default(obj: Any) -> Any:
        if isinstance(obj, (np.floating,)):
            v = float(obj)
            return None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
