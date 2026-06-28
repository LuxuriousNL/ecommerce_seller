"""Pricing engine tests, validated against the research report's worked examples."""

from __future__ import annotations

import pytest

from etsyshop.pricing import (
    US,
    CostInputs,
    break_even_price,
    evaluate,
    max_safe_discount_rate,
    price_for_margin,
    recommend_price,
    round_price,
)


def test_matches_report_mid_price_worked_example():
    """Report 1 mid example: order 47.95, direct cost 31.70 -> net ~9.80, margin ~20.5%."""
    c = CostInputs(
        product_cost=8.00,      # materials
        labor_cost=15.00,       # 0.60h * $25
        overhead=1.50,
        packaging=1.20,
        shipping_cost_to_seller=6.00,
        shipping_charged_to_buyer=0.0,
        return_reserve_rate=0.03,
    )
    b = evaluate(47.95, c, US)
    assert b.direct_cost == pytest.approx(31.70, abs=0.01)
    assert b.transaction_fee == pytest.approx(3.12, abs=0.01)
    assert b.payment_processing == pytest.approx(1.69, abs=0.01)
    assert b.return_reserve == pytest.approx(1.44, abs=0.01)
    assert b.net_profit == pytest.approx(9.80, abs=0.02)
    assert b.net_margin == pytest.approx(0.205, abs=0.005)


def test_break_even_yields_zero_profit():
    c = CostInputs(product_cost=11.00, overhead=0.5)
    be = break_even_price(c, US)
    assert evaluate(be, c, US).net_profit == pytest.approx(0.0, abs=1e-6)


def test_price_for_margin_hits_target():
    c = CostInputs(product_cost=11.00, overhead=0.5)
    price = price_for_margin(c, US, 0.35)
    assert evaluate(price, c, US).net_margin == pytest.approx(0.35, abs=1e-6)


def test_price_rises_with_offsite_ads():
    base = CostInputs(product_cost=11.0)
    with_ads = CostInputs(product_cost=11.0, offsite_ads_rate=0.15)
    assert price_for_margin(with_ads, US, 0.35) > price_for_margin(base, US, 0.35)


def test_impossible_margin_raises():
    c = CostInputs(product_cost=11.0)
    with pytest.raises(ValueError):
        price_for_margin(c, US, 0.95)  # exceeds 1 - fee rates


def test_round_price_charm_and_prestige():
    assert round_price(23.4, "charm") == 23.99
    assert round_price(23.6, "prestige") == 24.0
    assert round_price(0.2, "charm") == 0.99  # floor


def test_max_safe_discount_is_zero_at_break_even():
    c = CostInputs(product_cost=11.0)
    be = break_even_price(c, US)
    assert max_safe_discount_rate(be, c, US) == pytest.approx(0.0, abs=1e-6)


def test_recommend_price_is_profitable_and_above_floor():
    c = CostInputs(product_cost=11.0, overhead=0.5)
    rec = recommend_price(c, US, target_margin=0.35, rounding="charm")
    assert rec.list_price == pytest.approx(round_price(rec.raw_price, "charm"))
    assert rec.breakdown.net_margin > 0.30
    assert rec.ad_safe_floor > rec.break_even  # ads raise the floor
    assert str(rec.list_price).endswith(".99")
    assert 0 < rec.max_safe_discount < 1
