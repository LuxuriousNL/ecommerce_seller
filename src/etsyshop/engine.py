"""The trend engine: traverse in-season niches and produce a campaign plan.

Composes trend selection -> ideation -> (listing) -> fee-aware pricing into a
plan you can review (dry run) or hand to the Printify pipeline. Ideation and
listing are injectable so the composition is testable without the Claude API.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Callable

from etsyshop.models import OptimizedListing, ProductConcept
from etsyshop.pricing import US, CostInputs, FeeSchedule, PriceRecommendation, recommend_price
from etsyshop.trends import ScoredNiche, TrendNiche, trending_now

# Rough POD cost-of-goods estimates by product type (USD), to be replaced with
# real Printify variant costs once a shop + blueprint are connected.
_COST_BY_KEYWORD = {
    "ornament": 5.0, "mug": 7.5, "poster": 6.0, "print": 6.0,
    "tote": 9.0, "bag": 9.0, "shirt": 11.0, "tee": 11.0,
}
_DEFAULT_COST = 8.0


def estimate_product_cost(concept: ProductConcept, niche: TrendNiche) -> float:
    # The concept's own product type wins; fall back to the niche's blueprint hint.
    for text in (concept.product_type.lower(), (niche.blueprint_hint or "").lower()):
        for keyword, cost in _COST_BY_KEYWORD.items():
            if keyword in text:
                return cost
    return _DEFAULT_COST


IdeateFn = Callable[[TrendNiche, int], list[ProductConcept]]
ListingFn = Callable[[ProductConcept], OptimizedListing]


@dataclass
class CampaignItem:
    niche_slug: str
    status: str  # peak | build | upcoming
    concept: ProductConcept
    price: PriceRecommendation
    in_market_band: bool
    listing: OptimizedListing | None = None


@dataclass
class CampaignPlan:
    generated_on: dt.date
    items: list[CampaignItem] = field(default_factory=list)

    @property
    def niches(self) -> list[str]:
        return sorted({i.niche_slug for i in self.items})


def plan_campaign(
    ideate_fn: IdeateFn,
    *,
    on: dt.date | None = None,
    count_per_niche: int = 2,
    max_niches: int = 3,
    printify_only: bool = True,
    target_margin: float = 0.40,
    fees: FeeSchedule = US,
    overhead: float = 1.0,
    listing_fn: ListingFn | None = None,
    skip_slugs: set[str] | None = None,
    niches: list[TrendNiche] | None = None,
) -> CampaignPlan:
    """Build a campaign plan from the niches in season on `on` (default today)."""
    on = on or dt.date.today()
    skip = skip_slugs or set()
    selected: list[ScoredNiche] = trending_now(
        on=on, printify_only=printify_only, niches=niches
    )[:max_niches]

    plan = CampaignPlan(generated_on=on)
    for scored in selected:
        niche = scored.niche
        for concept in ideate_fn(niche, count_per_niche):
            if concept.slug in skip:
                continue
            cost = estimate_product_cost(concept, niche)
            rec = recommend_price(
                CostInputs(product_cost=cost, overhead=overhead),
                fees,
                target_margin=target_margin,
                rounding="charm" if niche.price_high < 40 else "prestige",
            )
            in_band = niche.price_low <= rec.list_price <= niche.price_high
            plan.items.append(
                CampaignItem(
                    niche_slug=niche.slug,
                    status=scored.status,
                    concept=concept,
                    price=rec,
                    in_market_band=in_band,
                    listing=listing_fn(concept) if listing_fn else None,
                )
            )
    return plan
