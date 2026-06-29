"""Live wiring for the growth orchestrator — real modules end-to-end.

`build_live_steps()` returns GrowthSteps backed by the actual modules:
  ideate (Claude) -> design+QC -> price -> publish (Etsy) -> advertise (adsuite)
  -> measure (profit from orders) -> decide -> act (kill losers).

Digital niches run fully automatically. POD (physical) publishing needs a
ProductTemplate with real Printify catalog ids, so it's supplied via `templates`
(or a `pod_publish_fn`); without one, that concept is skipped with a clear reason.

Every sub-step is injectable so the composition is unit-tested offline.
"""

from __future__ import annotations

from typing import Callable

from etsyshop.growth import GrowthSteps
from etsyshop.models import ProductTemplate
from etsyshop.pricing import US, CostInputs, FeeSchedule, recommend_price


def make_concept(
    concept,
    *,
    etsy,
    niches: dict,
    fees: FeeSchedule = US,
    target_margin: float = 0.40,
    optimize_fn: Callable,
    design_fn: Callable,
    publish_digital_fn: Callable,
    save_fn: Callable,
    pod_publish_fn: Callable | None = None,
) -> dict:
    """optimize -> design+QC -> price -> publish. Returns {ok, listing_id?, reason?}."""
    from etsyshop.engine import estimate_product_cost
    from etsyshop.publisher import draft_for_digital

    niche = niches.get(concept.niche_slug)
    template = ProductTemplate(name=concept.product_type, blueprint_id=0, print_provider_id=0)

    listing = optimize_fn(concept.to_design(), template)

    art = design_fn(concept.slug, concept.design, concept.product_type)
    if art.status == "qc_failed":
        return {"ok": False, "reason": "qc_failed"}
    if art.status == "error":
        return {"ok": False, "reason": f"design: {art.error}"}

    cost = estimate_product_cost(concept, niche) if niche else 8.0
    price = recommend_price(CostInputs(product_cost=cost), fees, target_margin=target_margin).list_price

    if niche and niche.kind == "digital":
        files = [str(art.path)] if art.path else []
        draft = draft_for_digital(
            listing, price=price,
            taxonomy_query=niche.etsy_taxonomy, attributes=niche.etsy_attributes,
            digital_files=files, image_paths=files)
        pub = publish_digital_fn(etsy, draft)
        if pub.listing_id and not pub.error:
            save_fn(concept.slug, pub.listing_id, "download")
            return {"ok": True, "listing_id": pub.listing_id}
        return {"ok": False, "reason": pub.error or "publish failed"}

    # POD (physical): needs a real catalog template.
    if pod_publish_fn is None:
        return {"ok": False, "reason": f"no POD template for '{concept.product_type}'"}
    return pod_publish_fn(concept, listing, price)


def build_live_steps(
    *,
    etsy,
    cfg=None,
    fees: FeeSchedule = US,
    target_margin: float = 0.40,
    run_ads: bool = True,
    pod_publish_fn: Callable | None = None,
    # injectable real defaults (overridden in tests)
    select_fn: Callable | None = None,
    ideate_fn: Callable | None = None,
    optimize_fn: Callable | None = None,
    design_fn: Callable | None = None,
    publish_digital_fn: Callable | None = None,
    advertise_fn: Callable | None = None,
    measure_fn: Callable | None = None,
    save_fn: Callable | None = None,
    act_fn: Callable | None = None,
) -> GrowthSteps:
    """Compose GrowthSteps from the real modules (with injectable overrides)."""
    from etsyshop.profit import decisions as profit_decisions
    from etsyshop.trends import load_trends, trending_now

    niches = {n.slug: n for n in load_trends()}

    if select_fn is None:
        select_fn = lambda: [s.niche for s in trending_now()]  # noqa: E731
    if ideate_fn is None:
        from etsyshop.ideate import ideate
        ideate_fn = ideate
    if optimize_fn is None:
        from etsyshop.optimize import optimize_listing
        optimize_fn = optimize_listing
    if design_fn is None:
        from etsyshop.design import create_design
        design_fn = lambda slug, brief, ptype: create_design(  # noqa: E731
            slug, brief, product_type=ptype, qc=True)
    if publish_digital_fn is None:
        from etsyshop.publisher import publish_listing
        publish_digital_fn = lambda e, draft: publish_listing(e, draft, activate=False)  # noqa: E731
    if save_fn is None:
        from etsyshop.store import ListingRecord, save_record
        save_fn = lambda slug, lid, kind: save_record(  # noqa: E731
            ListingRecord(etsy_listing_id=str(lid), slug=slug, kind=kind))
    if advertise_fn is None:
        advertise_fn = _default_advertise
    if measure_fn is None:
        measure_fn = lambda: _measure_from_etsy(etsy)  # noqa: E731
    if act_fn is None:
        act_fn = lambda ds: _act_kill_losers(ds, etsy=etsy)  # noqa: E731

    def make(concept):
        return make_concept(
            concept, etsy=etsy, niches=niches, fees=fees, target_margin=target_margin,
            optimize_fn=optimize_fn, design_fn=design_fn,
            publish_digital_fn=publish_digital_fn, save_fn=save_fn,
            pod_publish_fn=pod_publish_fn)

    def advertise(concept, budget):
        return advertise_fn(concept, budget) if run_ads else {"ok": False, "reason": "ads off"}

    return GrowthSteps(
        select_niches=select_fn, ideate=ideate_fn, make=make,
        advertise=advertise, measure=measure_fn,
        decide=lambda ledger: profit_decisions(ledger), act=act_fn)


def _default_advertise(concept, budget: float) -> dict:
    """Advertise a just-published listing (looks it up in the store by slug)."""
    from adsuite.channels.paid import launch_paid
    from adsuite.models import Creative
    from etsyshop.store import load_store

    rec = next((r for r in load_store().values() if r.slug == concept.slug), None)
    if not rec:
        return {"ok": False, "reason": "not published"}
    url = f"https://www.etsy.com/listing/{rec.etsy_listing_id}"
    creative = Creative(slug=concept.slug, landing_url=url,
                        paid_headline=concept.title_hint or concept.slug,
                        paid_primary_text=f"Ad. {concept.title_hint or concept.slug}")
    results = launch_paid(creative, channels=["meta_paid", "google_ads"],
                          daily_budget=budget, name=concept.slug, landing_url=url)
    return {"ok": any(r.ok for r in results.values()), "channels": list(results)}


def _measure_from_etsy(etsy) -> dict:
    from etsyshop.profit import build_ledger, revenue_units_from_receipts
    try:
        receipts = etsy.list_receipts().get("results") or []
    except Exception:  # noqa: BLE001
        receipts = []
    rev, units = revenue_units_from_receipts(receipts)
    return build_ledger(revenue_by_key=rev, units_by_key=units)


def _act_kill_losers(decisions, *, etsy) -> dict:
    """Deactivate listings the profit brain says to kill (scale is left to budget tools)."""
    actions: dict[str, str] = {}
    for d in decisions:
        if d.action == "kill":
            try:
                etsy.update_listing(d.key, state="inactive")
                actions[d.key] = "deactivated"
            except Exception as exc:  # noqa: BLE001
                actions[d.key] = f"kill-failed: {exc}"
        elif d.action == "scale":
            actions[d.key] = "scale (raise ad budget)"
    return actions
