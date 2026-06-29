"""Epic G: growth orchestrator engine + guardrails + dedupe."""

from __future__ import annotations

from types import SimpleNamespace

from etsyshop.growth import Guardrails, GrowthSteps, build_plan_steps, run_cycle
from etsyshop.profit import ProfitDecision


def make_steps(*, niches=2, concepts=2, make_result=None, measured=None):
    make_result = make_result or {"ok": True}

    def select():
        return [SimpleNamespace(slug=f"n{i}") for i in range(niches)]

    def ideate(niche, count):
        return [SimpleNamespace(slug=f"{niche.slug}-c{j}") for j in range(count)]

    calls = {"made": [], "advertised": [], "measured": 0, "acted": []}

    def make(concept):
        calls["made"].append(concept.slug)
        return make_result

    def advertise(concept, budget):
        calls["advertised"].append((concept.slug, budget))
        return {"ok": True}

    def measure():
        calls["measured"] += 1
        return measured or {}

    def decide(ledger):
        return [ProfitDecision("p1", "scale", "x")]

    def act(decisions):
        calls["acted"] = [d.key for d in decisions]
        return {d.key: d.action for d in decisions}

    steps = GrowthSteps(select_niches=select, ideate=ideate, make=make,
                        advertise=advertise, measure=measure, decide=decide, act=act)
    return steps, calls


def test_full_cycle_creates_advertises_and_closes_loop():
    steps, calls = make_steps(niches=2, concepts=2)
    report = run_cycle(steps, guardrails=Guardrails(max_new_products=10, max_daily_ad_spend=100),
                       concepts_per_niche=2, ad_budget=5.0)
    assert len(report.created) == 4
    assert len(report.advertised) == 4
    assert calls["measured"] == 1
    assert report.actions == {"p1": "scale"}  # measure->decide->act ran


def test_kill_switch_halts_before_anything():
    steps, calls = make_steps()
    report = run_cycle(steps, guardrails=Guardrails(kill_switch=True))
    assert report.halted and "kill switch" in report.halted
    assert report.created == [] and calls["measured"] == 0


def test_max_new_products_caps_creation_but_still_measures():
    steps, calls = make_steps(niches=3, concepts=3)
    report = run_cycle(steps, guardrails=Guardrails(max_new_products=2, max_daily_ad_spend=100),
                       concepts_per_niche=3)
    assert len(report.created) == 2
    assert report.halted == "max_new_products reached"
    assert calls["measured"] == 1  # loop still closed


def test_ad_spend_cap_limits_advertising():
    steps, _ = make_steps(niches=2, concepts=2)
    report = run_cycle(steps, guardrails=Guardrails(max_new_products=10, max_daily_ad_spend=10.0),
                       concepts_per_niche=2, ad_budget=5.0)
    assert len(report.created) == 4       # all created
    assert len(report.advertised) == 2    # only 2 * $5 fit under the $10 cap
    assert report.ad_spend_planned == 10.0


def test_qc_failure_halts_when_configured():
    steps, _ = make_steps(make_result={"ok": False, "reason": "qc_failed"})
    report = run_cycle(steps, guardrails=Guardrails(halt_on_qc_fail=True))
    assert report.halted and "QC" in report.halted
    assert report.created == []


def test_dedupe_skips_seen_slugs():
    steps, _ = make_steps(niches=1, concepts=2)
    report = run_cycle(steps, guardrails=Guardrails(max_new_products=10, max_daily_ad_spend=100),
                       seen_slugs={"n0-c0"}, concepts_per_niche=2)
    assert "n0-c0" in report.skipped
    assert report.created == ["n0-c1"]


def test_build_plan_steps_offline():
    import datetime as dt
    steps = build_plan_steps(on=dt.date(2026, 10, 1))
    niches = steps.select_niches()
    assert niches  # October has in-season niches
    concepts = steps.ideate(niches[0], 2)
    assert len(concepts) == 2 and steps.make(concepts[0])["ok"]
    assert steps.measure() == {} and steps.act([]) == {}
