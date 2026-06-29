"""Growth orchestrator: the closed loop.

Wires the existing modules into one cycle —
  select niches -> ideate -> make (design+QC+price+publish) -> advertise
  -> measure (profit) -> decide (scale/hold/kill) -> act
— with guardrails (caps, kill switch) and dedupe. Steps are injectable so the
engine is fully testable without real APIs; a default factory wires the real
modules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger("etsyshop.growth")


@dataclass
class Guardrails:
    max_new_products: int = 5
    max_daily_ad_spend: float = 20.0
    halt_on_qc_fail: bool = True
    kill_switch: bool = False


@dataclass
class GrowthSteps:
    select_niches: Callable[[], list]                 # () -> [niche]
    ideate: Callable[[object, int], list]             # (niche, count) -> [concept]
    make: Callable[[object], dict]                    # concept -> {ok, listing_id?, reason?}
    advertise: Callable[[object, float], dict]        # (concept, budget) -> {ok, campaign?}
    measure: Callable[[], dict]                       # () -> ledger {key: ProductPnL}
    decide: Callable[[dict], list]                    # ledger -> [ProfitDecision]
    act: Callable[[list], dict]                       # decisions -> {key: action}


@dataclass
class CycleReport:
    created: list[str] = field(default_factory=list)
    advertised: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    decisions: list = field(default_factory=list)
    actions: dict = field(default_factory=dict)
    ad_spend_planned: float = 0.0
    halted: str | None = None


def run_cycle(
    steps: GrowthSteps,
    *,
    guardrails: Guardrails | None = None,
    seen_slugs: set[str] | None = None,
    concepts_per_niche: int = 2,
    ad_budget: float = 5.0,
) -> CycleReport:
    """Run one growth cycle. Creation respects guardrails; measure/decide/act always run."""
    g = guardrails or Guardrails()
    report = CycleReport()
    if g.kill_switch:
        report.halted = "kill switch enabled"
        return report

    seen = set(seen_slugs or set())

    for niche in steps.select_niches():
        if report.halted:
            break
        for concept in steps.ideate(niche, concepts_per_niche):
            slug = getattr(concept, "slug", str(concept))
            if len(report.created) >= g.max_new_products:
                report.halted = "max_new_products reached"
                break
            if slug in seen:
                report.skipped.append(slug)
                continue

            made = steps.make(concept)
            if not made.get("ok"):
                report.skipped.append(slug)
                if g.halt_on_qc_fail and made.get("reason") == "qc_failed":
                    report.halted = f"halted on QC failure ({slug})"
                    break
                continue

            report.created.append(slug)
            seen.add(slug)
            log.info("growth: created %s", slug)

            # Advertise, respecting the cumulative daily ad-spend cap.
            if report.ad_spend_planned + ad_budget <= g.max_daily_ad_spend:
                adv = steps.advertise(concept, ad_budget)
                if adv.get("ok"):
                    report.advertised.append(slug)
                    report.ad_spend_planned = round(report.ad_spend_planned + ad_budget, 2)

    # Close the loop on existing products regardless of creation outcome.
    ledger = steps.measure()
    report.decisions = steps.decide(ledger)
    report.actions = steps.act(report.decisions)
    log.info("growth cycle: created=%d advertised=%d actions=%d",
             len(report.created), len(report.advertised), len(report.actions))
    return report


def build_plan_steps(*, on=None) -> GrowthSteps:
    """Offline, free 'dry-run' steps: real niche selection + profit decisions, but
    creation/advertising are simulated (no Claude / no external API calls)."""
    import datetime as dt
    from types import SimpleNamespace

    from etsyshop.profit import decisions as profit_decisions
    from etsyshop.trends import trending_now

    def select() -> list:
        return [s.niche for s in trending_now(on=on or dt.date.today())]

    def ideate(niche, count):
        return [SimpleNamespace(slug=f"{niche.slug}-{i}", niche=niche) for i in range(count)]

    return GrowthSteps(
        select_niches=select,
        ideate=ideate,
        make=lambda concept: {"ok": True, "simulated": True},
        advertise=lambda concept, budget: {"ok": True, "simulated": True},
        measure=lambda: {},                       # no live sales data offline
        decide=lambda ledger: profit_decisions(ledger),
        act=lambda decisions: {},
    )
