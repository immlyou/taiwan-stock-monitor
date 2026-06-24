"""成本價離群保護測試 — plausible_pnl_pct

成本價打錯／單位錯誤（例：160 元的股票成本存成 0.9）不可產生荒謬報酬率，
應回 None 讓呼叫端顯示為未知，而非毒化整體損益。
"""
import pytest

from app.components.portfolio_utils import PLAUSIBLE_PNL_RATIO, plausible_pnl_pct


def test_normal_gain():
    assert plausible_pnl_pct(107.15, 95.29) == pytest.approx(12.45, abs=0.01)


def test_normal_loss():
    assert plausible_pnl_pct(160.0, 164.0) == pytest.approx(-2.44, abs=0.01)


def test_large_but_plausible_gain_kept():
    # ~7.2x（+619.8%）仍在 20x 門檻內，視為真實長期報酬，保留。
    assert plausible_pnl_pct(92.35, 12.83) == pytest.approx(619.8, abs=0.1)


@pytest.mark.parametrize("current,cost", [
    (160.0, 0.9),     # 17677% — 成本打錯
    (1070.0, 0.81),   # 131998%
    (32.84, 0.81),    # 3954%
])
def test_absurd_cost_returns_none(current, cost):
    assert plausible_pnl_pct(current, cost) is None


@pytest.mark.parametrize("current,cost", [
    (160.0, 0.0),     # 成本為 0
    (160.0, -5.0),    # 成本為負
    (0.0, 100.0),     # 現價為 0（無資料）
    (160.0, None),    # 缺失
    (None, 100.0),
    (160.0, "abc"),   # 非數值
])
def test_invalid_inputs_return_none(current, cost):
    assert plausible_pnl_pct(current, cost) is None


def test_threshold_boundary():
    # 剛好在門檻內外：ratio = PLAUSIBLE_PNL_RATIO 視為合理，略超則 None。
    assert plausible_pnl_pct(PLAUSIBLE_PNL_RATIO * 10.0, 10.0) is not None
    assert plausible_pnl_pct(PLAUSIBLE_PNL_RATIO * 10.0 + 1.0, 10.0) is None
    # 反向（成本遠高於現價）同樣判定異常。
    assert plausible_pnl_pct(10.0, PLAUSIBLE_PNL_RATIO * 10.0 + 1.0) is None
