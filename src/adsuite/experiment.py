"""A/B experiment engine: launch two variants, compare, double down on the winner.

Capability 3: run two products as parallel paid campaigns across channels,
collect normalized metrics, decide a winner under a rule with a min-sample
guard, then scale the winner's budget and pause the loser.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from adsuite.channels.paid import make_paid_channel
from adsuite.config import AdSettings
from adsuite.models import Campaign, Creative, DecisionRule, Experiment, Metrics

log = logging.getLogger("adsuite.experiment")

ChannelFactory = Callable[[str, AdSettings | None], object]


@dataclass
class LaunchedExperiment:
    experiment_slug: str
    # variant_label -> channel -> campaign_id
    campaigns: dict[str, dict[str, str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def launch_experiment(
    experiment: Experiment,
    creatives: dict[str, Creative],   # variant_label -> Creative
    *,
    max_daily_budget: float = 20.0,
    cfg: AdSettings | None = None,
    channel_factory: ChannelFactory = make_paid_channel,
) -> LaunchedExperiment:
    """Create one campaign per variant per channel; budget split evenly across variants."""
    launched = LaunchedExperiment(experiment_slug=experiment.slug)
    per_variant_budget = experiment.daily_budget / 2.0
    if per_variant_budget > max_daily_budget:
        launched.errors.append(
            f"per-variant budget {per_variant_budget} exceeds max {max_daily_budget}")
        return launched

    for variant in (experiment.variant_a, experiment.variant_b):
        creative = creatives[variant.label]
        launched.campaigns[variant.label] = {}
        for ch_name in experiment.channels:
            campaign = Campaign(
                name=f"{experiment.slug}-{variant.label}-{ch_name}",
                channel=ch_name, objective=experiment.objective,
                daily_budget=per_variant_budget, landing_url=creative.landing_url)
            result = channel_factory(ch_name, cfg).create_campaign(campaign, creative)
            if result.ok:
                cid = result.ids.get("campaign") or str(result.ids)
                launched.campaigns[variant.label][ch_name] = str(cid)
            else:
                launched.errors.append(f"{variant.label}/{ch_name}: {result.error}")
    return launched


def collect_insights(
    launched: LaunchedExperiment,
    *,
    cfg: AdSettings | None = None,
    channel_factory: ChannelFactory = make_paid_channel,
) -> dict[str, Metrics]:
    """Aggregate metrics per variant across its channels."""
    totals: dict[str, Metrics] = {}
    for label, by_channel in launched.campaigns.items():
        agg = Metrics()
        for ch_name, campaign_id in by_channel.items():
            m = channel_factory(ch_name, cfg).insights(campaign_id)
            agg = Metrics(
                impressions=agg.impressions + m.impressions,
                clicks=agg.clicks + m.clicks,
                spend=agg.spend + m.spend,
                conversions=agg.conversions + m.conversions,
                revenue=agg.revenue + m.revenue,
            )
        totals[label] = agg
    return totals


@dataclass
class Decision:
    winner: str | None          # variant label, or None
    loser: str | None
    inconclusive: bool
    reason: str


def _score(metrics: Metrics, rule: DecisionRule) -> float:
    if rule.metric == "cpa":
        return metrics.cpa            # lower is better
    if rule.metric == "roas":
        return metrics.roas           # higher is better
    return metrics.ctr                # higher is better


def _meets_sample(metrics: Metrics, rule: DecisionRule) -> bool:
    return metrics.spend >= rule.min_spend and metrics.conversions >= rule.min_conversions


def decide(metrics: dict[str, Metrics], rule: DecisionRule) -> Decision:
    """Pick a winner under the rule, guarding against premature calls."""
    labels = list(metrics)
    if len(labels) != 2:
        return Decision(None, None, True, "need exactly two variants")
    a, b = labels
    if not (_meets_sample(metrics[a], rule) and _meets_sample(metrics[b], rule)):
        return Decision(None, None, True,
                        f"min sample not met (need spend>={rule.min_spend}, "
                        f"conversions>={rule.min_conversions} per variant)")

    sa, sb = _score(metrics[a], rule), _score(metrics[b], rule)
    lower_wins = rule.metric == "cpa"
    # Determine better/worse and the relative margin between them.
    if lower_wins:
        winner, loser, best, worst = (a, b, sa, sb) if sa < sb else (b, a, sb, sa)
        margin = (worst - best) / worst if worst else 0.0
    else:
        winner, loser, best, worst = (a, b, sa, sb) if sa > sb else (b, a, sb, sa)
        margin = (best - worst) / best if best else 0.0

    if margin < rule.margin:
        return Decision(None, None, True,
                        f"margin {margin:.2%} below threshold {rule.margin:.2%}")
    log.info("experiment decision: %s wins on %s by %.2f%%", winner, rule.metric, margin * 100)
    return Decision(winner, loser, False,
                    f"{winner} wins on {rule.metric} by {margin:.2%}")


def act_on_decision(
    decision: Decision,
    launched: LaunchedExperiment,
    *,
    scale_factor: float = 2.0,
    winner_daily_budget: float = 10.0,
    cfg: AdSettings | None = None,
    channel_factory: ChannelFactory = make_paid_channel,
) -> dict[str, str]:
    """Scale the winner's budget and pause the loser. Returns per-campaign actions."""
    actions: dict[str, str] = {}
    if decision.inconclusive or not decision.winner:
        return actions
    for ch_name, cid in launched.campaigns.get(decision.winner, {}).items():
        channel_factory(ch_name, cfg).set_budget(cid, winner_daily_budget * scale_factor)
        actions[f"{decision.winner}/{ch_name}"] = "scaled"
    for ch_name, cid in launched.campaigns.get(decision.loser, {}).items():
        channel_factory(ch_name, cfg).pause(cid)
        actions[f"{decision.loser}/{ch_name}"] = "paused"
    return actions
