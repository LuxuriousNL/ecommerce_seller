"""Trend-engine composition tests: ideation + pricing into a campaign plan."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from etsyshop.config import settings
from etsyshop.engine import estimate_product_cost, plan_campaign
from etsyshop.ideate import Concepts, ideate
from etsyshop.models import DesignBrief, ProductConcept, ProductTemplate
from etsyshop.trends import TrendNiche, load_trends


def make_concept(slug: str, product_type: str = "Ceramic Ornament") -> ProductConcept:
    return ProductConcept(
        slug=slug,
        product_type=product_type,
        niche_slug="x",
        micro_positioning="family + pets",
        title_hint="Custom Family Ornament",
        seed_keywords=["family ornament", "custom name"],
        design=DesignBrief(subject="family name bauble", style="minimalist line art",
                           palette="warm neutrals"),
    )


def fake_ideate(niche: TrendNiche, count: int) -> list[ProductConcept]:
    return [make_concept(f"{niche.slug}-{i}") for i in range(count)]


def test_estimate_cost_by_product_type():
    niche = next(n for n in load_trends() if n.slug == "personalised-ornaments")
    assert estimate_product_cost(make_concept("a", "Ceramic Ornament"), niche) == 5.0
    assert estimate_product_cost(make_concept("b", "Coffee Mug"), niche) == 7.5


def test_plan_prices_concepts_and_flags_band():
    # October -> POD niches at peak (ornaments, pet-memorial).
    plan = plan_campaign(
        fake_ideate, on=dt.date(2026, 10, 1), count_per_niche=2, max_niches=2,
        printify_only=True, target_margin=0.40,
    )
    assert plan.items, "expected a non-empty plan"
    assert {i.status for i in plan.items} == {"peak"}
    for item in plan.items:
        assert item.price.list_price > 0
        assert item.price.breakdown.net_margin > 0.30
        # ornaments sit in the $9-28 band; a $5 COGS ornament should land in-band
        assert item.in_market_band


def test_plan_respects_skip_slugs():
    plan = plan_campaign(
        fake_ideate, on=dt.date(2026, 10, 1), count_per_niche=2, max_niches=1,
        skip_slugs={"personalised-ornaments-0"},
    )
    slugs = {i.concept.slug for i in plan.items}
    assert "personalised-ornaments-0" not in slugs
    assert "personalised-ornaments-1" in slugs


def test_template_resolves_price_from_engine():
    tmpl = ProductTemplate(
        name="Tee", blueprint_id=6, print_provider_id=99, variant_ids=[1],
        product_cost=11.0, target_margin=0.35,
    )
    cents = tmpl.resolve_price_cents()
    assert cents > 1100  # above COGS
    # falls back to the constant when costs aren't provided
    plain = ProductTemplate(name="Tee", blueprint_id=6, print_provider_id=99, price_cents=2499)
    assert plain.resolve_price_cents() == 2499


class FakeAnthropic:
    def __init__(self, concepts):
        self.messages = SimpleNamespace(
            parse=lambda **kw: SimpleNamespace(parsed_output=Concepts(concepts=concepts))
        )


def test_ideate_links_niche_slug(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    niche = next(n for n in load_trends() if n.slug == "halloween-svg")
    raw = [make_concept("retro-ghost"), make_concept("goth-bat")]
    out = ideate(niche, 2, client=FakeAnthropic(raw))
    assert [c.slug for c in out] == ["retro-ghost", "goth-bat"]
    assert all(c.niche_slug == "halloween-svg" for c in out)  # relinked to the niche
