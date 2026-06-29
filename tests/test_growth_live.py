"""Live growth wiring: make_concept + build_live_steps composition (mocked)."""

from __future__ import annotations

from types import SimpleNamespace

from etsyshop.growth_live import build_live_steps, make_concept
from etsyshop.models import DesignBrief, OptimizedListing, ProductConcept
from etsyshop.profit import ProfitDecision


def _concept(slug="ghost", niche_slug="halloween-svg", ptype="SVG"):
    return ProductConcept(slug=slug, product_type=ptype, niche_slug=niche_slug,
                          title_hint="Spooky Ghost",
                          design=DesignBrief(subject="ghost", style="flat", palette="pink"))


DIGITAL_NICHE = SimpleNamespace(slug="halloween-svg", kind="digital",
                                etsy_taxonomy="Digital Prints", blueprint_hint=None,
                                etsy_attributes={"Occasion": "Halloween"})
POD_NICHE = SimpleNamespace(slug="personalised-ornaments", kind="pod",
                            etsy_taxonomy="Ornaments", etsy_attributes={}, blueprint_hint="Ornament")

LISTING = OptimizedListing(title="Ghost SVG", tags=["ghost svg"], description="d", materials=[])


def _deps(**over):
    saved = []
    base = dict(
        etsy=object(),
        niches={"halloween-svg": DIGITAL_NICHE, "personalised-ornaments": POD_NICHE},
        optimize_fn=lambda design, tmpl: LISTING,
        design_fn=lambda slug, brief, ptype: SimpleNamespace(status="ready", path="art/x.png", error=None),
        publish_digital_fn=lambda etsy, draft: SimpleNamespace(listing_id="L1", error=None),
        save_fn=lambda slug, lid, kind: saved.append((slug, lid, kind)),
    )
    base.update(over)
    return base, saved


def test_make_digital_concept_publishes_and_records():
    deps, saved = _deps()
    res = make_concept(_concept(), **deps)
    assert res == {"ok": True, "listing_id": "L1"}
    assert saved == [("ghost", "L1", "download")]


def test_make_halts_on_qc_failure():
    deps, _ = _deps(design_fn=lambda *a: SimpleNamespace(status="qc_failed", path=None, error=None))
    res = make_concept(_concept(), **deps)
    assert res == {"ok": False, "reason": "qc_failed"}


def test_make_reports_publish_error():
    deps, _ = _deps(publish_digital_fn=lambda etsy, draft: SimpleNamespace(listing_id=None, error="boom"))
    res = make_concept(_concept(), **deps)
    assert res["ok"] is False and "boom" in res["reason"]


def test_make_pod_without_template_is_skipped():
    deps, _ = _deps()
    res = make_concept(_concept(slug="orn", niche_slug="personalised-ornaments", ptype="Ceramic Ornament"),
                       **deps)
    assert res["ok"] is False and "no POD template" in res["reason"]


def test_make_pod_with_publish_fn():
    deps, _ = _deps(pod_publish_fn=lambda concept, listing, price: {"ok": True, "listing_id": "P9"})
    res = make_concept(_concept(slug="orn", niche_slug="personalised-ornaments", ptype="Ornament"),
                       **deps)
    assert res == {"ok": True, "listing_id": "P9"}


def test_build_live_steps_composition_runs_a_cycle():
    from etsyshop.growth import Guardrails, run_cycle

    steps = build_live_steps(
        etsy=object(),
        select_fn=lambda: [DIGITAL_NICHE],
        ideate_fn=lambda niche, count: [_concept(slug=f"g{i}") for i in range(count)],
        optimize_fn=lambda design, tmpl: LISTING,
        design_fn=lambda slug, brief, ptype: SimpleNamespace(status="ready", path="x.png", error=None),
        publish_digital_fn=lambda etsy, draft: SimpleNamespace(listing_id="L1", error=None),
        save_fn=lambda slug, lid, kind: None,
        advertise_fn=lambda concept, budget: {"ok": True},
        measure_fn=lambda: {},
        act_fn=lambda ds: {"x": "scale (raise ad budget)"},
    )
    report = run_cycle(steps, guardrails=Guardrails(max_new_products=2, max_daily_ad_spend=100),
                       concepts_per_niche=2, ad_budget=5.0)
    assert len(report.created) == 2 and len(report.advertised) == 2
    assert report.actions == {"x": "scale (raise ad budget)"}


def test_act_kill_losers_deactivates():
    from etsyshop.growth_live import _act_kill_losers

    class FakeEtsy:
        def __init__(self):
            self.deactivated = []

        def update_listing(self, listing_id, *, state=None, **kw):
            self.deactivated.append((listing_id, state))

    etsy = FakeEtsy()
    actions = _act_kill_losers(
        [ProfitDecision("L1", "kill", "x"), ProfitDecision("L2", "scale", "y")], etsy=etsy)
    assert actions["L1"] == "deactivated" and etsy.deactivated == [("L1", "inactive")]
    assert "scale" in actions["L2"]
