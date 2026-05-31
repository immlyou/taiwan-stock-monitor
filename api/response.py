"""自訂 FastAPI JSONResponse：自動將 NaN/Infinity/numpy 型別轉為 JSON-safe"""
from __future__ import annotations

import json as _json
import math
from typing import Any

import numpy as np
from fastapi.responses import JSONResponse


class SafeJSONResponse(JSONResponse):
    """自動將 NaN/Infinity 替換為 null 的 JSON Response"""

    def render(self, content: Any) -> bytes:
        return _json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            default=self._default,
        ).encode("utf-8")

    @staticmethod
    def _default(obj: Any) -> Any:
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, (np.floating,)):
            v = float(obj)
            return None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
