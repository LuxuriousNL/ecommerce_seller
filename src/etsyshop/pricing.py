"""Fee-aware Etsy pricing engine.

Models Etsy's published fee stack and solves for break-even and target-margin
prices. Rates are from Etsy's current fee schedule (see deep-research report 1):
$0.20 listing fee, 6.5% transaction fee on the order total (item + shipping +
gift wrap), country-specific payment processing, optional Offsite Ads (12/15%,
capped $100), and country regulatory operating fees.

All money is in the shop's currency as floats; round only at the end.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

TRANSACTION_RATE = 0.065
LISTING_FEE = 0.20
OFFSITE_ADS_CAP = 100.0


@dataclass(frozen=True)
class FeeSchedule:
    """Country-specific fee rates. Payment rates are Etsy's published examples."""

    country: str
    payment_pct: float
    payment_fixed: float
    regulatory_rate: float = 0.0
    currency: str = "USD"
    transaction_rate: float = TRANSACTION_RATE
    listing_fee: float = LISTING_FEE


# Published payment-processing rates (report 1). Add more only with real rates.
US = FeeSchedule("US", 0.03, 0.25, currency="USD")
UK = FeeSchedule("UK", 0.04, 0.20, regulatory_rate=0.0048, currency="GBP")
NL = FeeSchedule("NL", 0.04, 0.30, currency="EUR")
FR = FeeSchedule("FR", 0.04, 0.30, regulatory_rate=0.0114, currency="EUR")

SCHEDULES: dict[str, FeeSchedule] = {s.country: s for s in (US, UK, NL, FR)}


@dataclass
class CostInputs:
    """Per-unit cost structure. For POD, `product_cost` is the Printify base cost."""

    product_cost: float
    overhead: float = 0.0
    packaging: float = 0.0
    shipping_cost_to_seller: float = 0.0
    shipping_charged_to_buyer: float = 0.0
    gift_wrap: float = 0.0
    labor_cost: float = 0.0  # 0 for POD; used for handmade
    return_reserve_rate: float = 0.03
    offsite_ads_rate: float = 0.0  # 0.0, 0.12 (>=$10k), or 0.15 (<$10k)

    def direct_cost(self) -> float:
        return (
            self.product_cost
            + self.labor_cost
            + self.overhead
            + self.packaging
            + self.shipping_cost_to_seller
        )


@dataclass
class PriceBreakdown:
    item_price: float
    order_total: float
    direct_cost: float
    listing_fee: float
    transaction_fee: float
    payment_processing: float
    offsite_ads_fee: float
    regulatory_fee: float
    return_reserve: float
    net_profit: float
    net_margin: float
    currency: str = "USD"


def evaluate(item_price: float, c: CostInputs, fees: FeeSchedule) -> PriceBreakdown:
    """Compute the full fee breakdown and net profit for a given item price."""
    order_total = item_price + c.shipping_charged_to_buyer + c.gift_wrap
    transaction_fee = order_total * fees.transaction_rate
    payment_processing = order_total * fees.payment_pct + fees.payment_fixed
    offsite_ads_fee = min(order_total * c.offsite_ads_rate, OFFSITE_ADS_CAP)
    regulatory_fee = order_total * fees.regulatory_rate
    return_reserve = order_total * c.return_reserve_rate
    direct = c.direct_cost()

    net_profit = (
        order_total
        - direct
        - return_reserve
        - fees.listing_fee
        - transaction_fee
        - payment_processing
        - offsite_ads_fee
        - regulatory_fee
    )
    net_margin = net_profit / order_total if order_total else 0.0
    return PriceBreakdown(
        item_price=item_price,
        order_total=order_total,
        direct_cost=direct,
        listing_fee=fees.listing_fee,
        transaction_fee=transaction_fee,
        payment_processing=payment_processing,
        offsite_ads_fee=offsite_ads_fee,
        regulatory_fee=regulatory_fee,
        return_reserve=return_reserve,
        net_profit=net_profit,
        net_margin=net_margin,
        currency=fees.currency,
    )


def _rate_sum(c: CostInputs, fees: FeeSchedule) -> float:
    """Proportional rates applied to the order total."""
    return (
        c.return_reserve_rate
        + fees.transaction_rate
        + fees.payment_pct
        + c.offsite_ads_rate
        + fees.regulatory_rate
    )


def _fixed_costs(c: CostInputs, fees: FeeSchedule) -> float:
    return c.direct_cost() + fees.listing_fee + fees.payment_fixed


def break_even_price(c: CostInputs, fees: FeeSchedule) -> float:
    """The item price at which net profit is zero."""
    order_total = _fixed_costs(c, fees) / (1 - _rate_sum(c, fees))
    return order_total - c.shipping_charged_to_buyer - c.gift_wrap


def price_for_margin(c: CostInputs, fees: FeeSchedule, target_margin: float) -> float:
    """The item price that yields `target_margin` net margin."""
    denom = 1 - _rate_sum(c, fees) - target_margin
    if denom <= 0:
        raise ValueError("Target margin too high for this cost/fee structure.")
    order_total = _fixed_costs(c, fees) / denom
    return order_total - c.shipping_charged_to_buyer - c.gift_wrap


def max_safe_discount_rate(item_price: float, c: CostInputs, fees: FeeSchedule) -> float:
    """Largest discount that still breaks even, given a list price."""
    order_total = item_price + c.shipping_charged_to_buyer + c.gift_wrap
    if order_total <= 0:
        return 0.0
    be = break_even_price(c, fees) + c.shipping_charged_to_buyer + c.gift_wrap
    return max(0.0, 1 - be / order_total)


def round_price(price: float, style: str = "charm") -> float:
    """charm -> nearest x.99 (entry/mid); prestige -> whole number (premium)."""
    if style == "prestige":
        return float(max(1, round(price)))
    # charm: round up to the next whole, then subtract a penny -> x.99
    return max(0.99, math.ceil(price) - 0.01)


@dataclass
class PriceRecommendation:
    raw_price: float
    list_price: float
    rounding: str
    break_even: float
    ad_safe_floor: float  # break-even assuming Offsite Ads attribution
    breakdown: PriceBreakdown
    max_safe_discount: float = field(default=0.0)


def recommend_price(
    c: CostInputs,
    fees: FeeSchedule,
    *,
    target_margin: float = 0.35,
    rounding: str = "charm",
    offsite_ads_rate_for_floor: float = 0.15,
) -> PriceRecommendation:
    """Recommend a list price for a target margin, with a fee-aware breakdown.

    `ad_safe_floor` is the break-even price if the order is later attributed to
    Offsite Ads — the price you must stay above to avoid an ad-driven loss.
    """
    raw = price_for_margin(c, fees, target_margin)
    list_price = round_price(raw, rounding)

    ad_costs = CostInputs(**{**c.__dict__, "offsite_ads_rate": offsite_ads_rate_for_floor})
    return PriceRecommendation(
        raw_price=raw,
        list_price=list_price,
        rounding=rounding,
        break_even=break_even_price(c, fees),
        ad_safe_floor=break_even_price(ad_costs, fees),
        breakdown=evaluate(list_price, c, fees),
        max_safe_discount=max_safe_discount_rate(list_price, c, fees),
    )
