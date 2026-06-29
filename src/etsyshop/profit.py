"""Profitability brain: true net P&L per product, and scale/hold/kill decisions.

Unifies revenue (orders), COGS (Printify), platform fees (Etsy/Shopify), ad
spend (adsuite), and a returns reserve into contribution margin — the signal the
growth orchestrator and Shopify store-gating consult.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from etsyshop.analytics import rank_listings
from etsyshop.pricing import US, FeeSchedule


class ProductPnL(BaseModel):
    key: str
    units: int = 0
    revenue: float = 0.0
    cogs: float = 0.0
    platform_fees: float = 0.0
    ad_spend: float = 0.0
    returns_reserve: float = 0.0

    @property
    def net_profit(self) -> float:
        return round(self.revenue - self.cogs - self.platform_fees
                     - self.ad_spend - self.returns_reserve, 2)

    @property
    def margin(self) -> float:
        return self.net_profit / self.revenue if self.revenue else 0.0


def estimate_platform_fees(revenue: float, *, fees: FeeSchedule = US, orders: int = 1) -> float:
    """Approximate marketplace fees on revenue (transaction + payment + regulatory + listing)."""
    if revenue <= 0:
        return 0.0
    return round(
        revenue * (fees.transaction_rate + fees.payment_pct + fees.regulatory_rate)
        + fees.payment_fixed * orders + fees.listing_fee * orders, 2)


def build_ledger(
    *,
    revenue_by_key: dict[str, float],
    units_by_key: dict[str, int] | None = None,
    cogs_by_key: dict[str, float] | None = None,
    ad_spend_by_key: dict[str, float] | None = None,
    fees: FeeSchedule = US,
    returns_rate: float = 0.03,
) -> dict[str, ProductPnL]:
    """Assemble a per-product P&L ledger from normalized component dicts."""
    units_by_key = units_by_key or {}
    cogs_by_key = cogs_by_key or {}
    ad_spend_by_key = ad_spend_by_key or {}
    ledger: dict[str, ProductPnL] = {}
    for key in set(revenue_by_key) | set(ad_spend_by_key) | set(cogs_by_key):
        rev = revenue_by_key.get(key, 0.0)
        units = units_by_key.get(key, 0)
        ledger[key] = ProductPnL(
            key=key, units=units, revenue=rev,
            cogs=cogs_by_key.get(key, 0.0),
            platform_fees=estimate_platform_fees(rev, fees=fees, orders=max(units, 1)),
            ad_spend=ad_spend_by_key.get(key, 0.0),
            returns_reserve=round(rev * returns_rate, 2),
        )
    return ledger


def ad_components_from_metrics(
    metrics_by_key: dict,
) -> tuple[dict[str, float], dict[str, float], dict[str, int]]:
    """Map ad metrics (duck-typed .spend/.revenue/.conversions, e.g. adsuite/pixel)
    into (ad_spend_by_key, revenue_by_key, units_by_key) for build_ledger."""
    ad_spend = {k: float(getattr(m, "spend", 0.0)) for k, m in metrics_by_key.items()}
    revenue = {k: float(getattr(m, "revenue", 0.0)) for k, m in metrics_by_key.items()}
    units = {k: int(getattr(m, "conversions", 0)) for k, m in metrics_by_key.items()}
    return ad_spend, revenue, units


def revenue_units_from_receipts(receipts: list[dict]) -> tuple[dict[str, float], dict[str, int]]:
    """Revenue + units per listing id from Etsy receipts (reuses analytics)."""
    perf = rank_listings(receipts)
    return ({p.listing_id: p.revenue for p in perf}, {p.listing_id: p.units for p in perf})


@dataclass
class ProfitDecision:
    key: str
    action: str  # scale | hold | kill
    reason: str


def classify(pnl: ProductPnL, *, scale_margin: float = 0.25, min_units: int = 3) -> ProfitDecision:
    if pnl.units < min_units:
        return ProfitDecision(pnl.key, "hold", f"insufficient data ({pnl.units} units)")
    if pnl.net_profit < 0:
        return ProfitDecision(pnl.key, "kill", f"unprofitable (net {pnl.net_profit})")
    if pnl.margin >= scale_margin:
        return ProfitDecision(pnl.key, "scale", f"margin {pnl.margin:.0%} >= {scale_margin:.0%}")
    return ProfitDecision(pnl.key, "hold", f"margin {pnl.margin:.0%} below scale threshold")


def rank(ledger: dict[str, ProductPnL]) -> list[ProductPnL]:
    return sorted(ledger.values(), key=lambda p: p.net_profit, reverse=True)


def decisions(ledger: dict[str, ProductPnL], **kw) -> list[ProfitDecision]:
    return [classify(p, **kw) for p in rank(ledger)]
