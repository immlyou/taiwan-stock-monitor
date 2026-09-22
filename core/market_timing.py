"""Fail-closed time slicing shared by model validation and strategy backtests."""
from __future__ import annotations

import pandas as pd


def as_of_frame(frame, cutoff: pd.Timestamp):
    """Slice availability-dated observations; reporting-period strings are unsafe.

    Callers must convert fiscal/month labels with the provider's publication-date
    API first. Parsing them as period-start dates would introduce look-ahead.
    A timestamp alone does not prove the source is revision-free point-in-time data.
    """
    if frame is None or frame.empty:
        return frame
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("回測資料必須使用資料可用日期的 DatetimeIndex，不接受報告期間索引")
    if frame.index.has_duplicates or frame.index.hasnans:
        raise ValueError("回測日期索引不可重複或缺失")
    cutoff = pd.Timestamp(cutoff)
    if frame.index.tz is not None and cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize(frame.index.tz)
    result = frame.loc[frame.index <= cutoff].sort_index()
    # FinlabDataFrame implicit index alignment can differ from plain pandas.
    return pd.DataFrame(result) if isinstance(frame, pd.DataFrame) else pd.Series(result)
