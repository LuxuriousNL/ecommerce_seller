"""Winner tracking: rank listings by sales so the planner can double down."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListingPerformance:
    listing_id: str
    units: int
    revenue: float


def _amount(price: object) -> float:
    """Etsy money is {amount, divisor}; tolerate a plain number too."""
    if isinstance(price, dict):
        divisor = price.get("divisor") or 100
        return price.get("amount", 0) / divisor
    if isinstance(price, (int, float)):
        return float(price)
    return 0.0


def rank_listings(receipts: list[dict]) -> list[ListingPerformance]:
    """Aggregate units + revenue per listing across receipts, best-selling first."""
    agg: dict[str, dict[str, float]] = {}
    for receipt in receipts:
        for txn in receipt.get("transactions") or []:
            lid = str(txn.get("listing_id"))
            qty = txn.get("quantity", 1) or 1
            bucket = agg.setdefault(lid, {"units": 0.0, "revenue": 0.0})
            bucket["units"] += qty
            bucket["revenue"] += _amount(txn.get("price")) * qty

    out = [
        ListingPerformance(lid, int(v["units"]), round(v["revenue"], 2))
        for lid, v in agg.items()
    ]
    out.sort(key=lambda p: (p.units, p.revenue), reverse=True)
    return out


def winners(receipts: list[dict], *, top: int = 10) -> list[ListingPerformance]:
    return rank_listings(receipts)[:top]
