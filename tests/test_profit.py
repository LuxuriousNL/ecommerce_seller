"""Epic P: profitability brain — P&L, ledger, decisions."""

from __future__ import annotations

from etsyshop.profit import (
    ProductPnL,
    build_ledger,
    classify,
    decisions,
    estimate_platform_fees,
    rank,
    revenue_units_from_receipts,
)


def test_pnl_net_and_margin():
    p = ProductPnL(key="a", units=10, revenue=200.0, cogs=60.0,
                   platform_fees=20.0, ad_spend=30.0, returns_reserve=6.0)
    assert p.net_profit == 84.0          # 200 - 60 - 20 - 30 - 6
    assert round(p.margin, 2) == 0.42
    assert ProductPnL(key="z").margin == 0.0  # no revenue


def test_estimate_platform_fees():
    fee = estimate_platform_fees(100.0, orders=1)
    # US: 6.5% txn + 3% pay + $0.25 + $0.20 listing = ~9.95
    assert 9.0 < fee < 11.0
    assert estimate_platform_fees(0.0) == 0.0


def test_build_ledger_assembles_components():
    ledger = build_ledger(
        revenue_by_key={"x": 100.0}, units_by_key={"x": 5},
        cogs_by_key={"x": 30.0}, ad_spend_by_key={"x": 15.0})
    p = ledger["x"]
    assert p.cogs == 30.0 and p.ad_spend == 15.0
    assert p.platform_fees > 0 and p.returns_reserve == 3.0  # 3% of 100
    assert p.net_profit == round(100 - 30 - p.platform_fees - 15 - 3, 2)


def test_revenue_units_from_receipts():
    receipts = [{"transactions": [
        {"listing_id": 100, "quantity": 2, "price": {"amount": 1299, "divisor": 100}}]}]
    rev, units = revenue_units_from_receipts(receipts)
    assert rev["100"] == 25.98 and units["100"] == 2


def test_classify_scale_hold_kill():
    scale = classify(ProductPnL(key="a", units=10, revenue=100, cogs=20,
                                platform_fees=10, ad_spend=5, returns_reserve=3))
    assert scale.action == "scale"

    kill = classify(ProductPnL(key="b", units=10, revenue=100, cogs=80,
                               platform_fees=10, ad_spend=30, returns_reserve=3))
    assert kill.action == "kill"  # negative net

    thin = classify(ProductPnL(key="c", units=10, revenue=100, cogs=60,
                               platform_fees=10, ad_spend=10, returns_reserve=3))
    assert thin.action == "hold"  # positive but below scale margin

    new = classify(ProductPnL(key="d", units=1, revenue=50))
    assert new.action == "hold" and "insufficient" in new.reason


def test_rank_and_decisions_order():
    ledger = build_ledger(
        revenue_by_key={"hi": 200.0, "lo": 50.0},
        units_by_key={"hi": 10, "lo": 10})
    ranked = rank(ledger)
    assert ranked[0].key == "hi"  # higher net first
    ds = decisions(ledger)
    assert [d.key for d in ds] == [p.key for p in ranked]
