"""Epic A4: A/B experiment launch, insights, decision, act-on-decision."""

from __future__ import annotations


from adsuite.channels.paid import normalize_google_insights, normalize_meta_insights
from adsuite.experiment import (
    act_on_decision,
    collect_insights,
    decide,
    launch_experiment,
)
from adsuite.models import (
    ChannelResult,
    Creative,
    DecisionRule,
    Experiment,
    ExperimentVariant,
    Metrics,
)


def _experiment() -> Experiment:
    return Experiment(
        slug="tee-vs-mug", channels=["meta_paid", "google_ads"], daily_budget=10.0,
        variant_a=ExperimentVariant(label="A", product_slug="tee", creative_slug="tee-c"),
        variant_b=ExperimentVariant(label="B", product_slug="mug", creative_slug="mug-c"),
    )


CREATIVES = {
    "A": Creative(slug="tee-c", product_slug="tee", landing_url="https://etsy/1"),
    "B": Creative(slug="mug-c", product_slug="mug", landing_url="https://etsy/2"),
}


class FakeChannel:
    """Records create/pause/set_budget and returns canned insights per campaign id."""

    created: list = []
    paused: list = []
    budgets: list = []

    def __init__(self, name, metrics_by_id=None):
        self.name = name
        self._metrics = metrics_by_id or {}

    def create_campaign(self, campaign, creative):
        FakeChannel.created.append((self.name, campaign.name, campaign.daily_budget))
        return ChannelResult(ok=True, ids={"campaign": f"{self.name}:{campaign.name}"})

    def pause(self, campaign_id):
        FakeChannel.paused.append((self.name, campaign_id))
        return ChannelResult(ok=True)

    def set_budget(self, object_id, daily_budget):
        FakeChannel.budgets.append((self.name, object_id, daily_budget))
        return ChannelResult(ok=True)

    def insights(self, campaign_id):
        return self._metrics.get(campaign_id, Metrics())


def test_launch_creates_campaign_per_variant_per_channel():
    FakeChannel.created = []
    launched = launch_experiment(
        _experiment(), CREATIVES, channel_factory=lambda name, cfg: FakeChannel(name))
    assert set(launched.campaigns) == {"A", "B"}
    assert set(launched.campaigns["A"]) == {"meta_paid", "google_ads"}
    # 2 variants * 2 channels = 4 campaigns, each at half the total budget
    assert len(FakeChannel.created) == 4
    assert all(budget == 5.0 for _, _, budget in FakeChannel.created)


def test_launch_budget_guard():
    exp = _experiment()
    exp.daily_budget = 100.0  # per-variant 50 > max 20
    launched = launch_experiment(exp, CREATIVES, max_daily_budget=20.0,
                                 channel_factory=lambda name, cfg: FakeChannel(name))
    assert launched.campaigns == {} and launched.errors


def test_collect_insights_aggregates_across_channels():
    launched = launch_experiment(
        _experiment(), CREATIVES, channel_factory=lambda name, cfg: FakeChannel(name))
    metrics = {
        "meta_paid:tee-vs-mug-A-meta_paid": Metrics(impressions=500, clicks=25, spend=10, conversions=5),
        "google_ads:tee-vs-mug-A-google_ads": Metrics(impressions=300, clicks=15, spend=5, conversions=2),
    }
    totals = collect_insights(launched, channel_factory=lambda name, cfg: FakeChannel(name, metrics))
    assert totals["A"].impressions == 800   # 500 + 300
    assert totals["A"].conversions == 7


def test_decide_winner_lower_cpa():
    rule = DecisionRule(metric="cpa", min_spend=10, min_conversions=5, margin=0.10)
    metrics = {
        "A": Metrics(spend=20, conversions=10),  # cpa 2.0
        "B": Metrics(spend=20, conversions=5),   # cpa 4.0
    }
    d = decide(metrics, rule)
    assert d.winner == "A" and d.loser == "B" and not d.inconclusive


def test_decide_inconclusive_below_sample():
    rule = DecisionRule(min_spend=50, min_conversions=20)
    metrics = {"A": Metrics(spend=10, conversions=2), "B": Metrics(spend=10, conversions=1)}
    assert decide(metrics, rule).inconclusive


def test_decide_inconclusive_below_margin():
    rule = DecisionRule(metric="cpa", min_spend=10, min_conversions=5, margin=0.25)
    metrics = {"A": Metrics(spend=20, conversions=10), "B": Metrics(spend=21, conversions=10)}
    assert decide(metrics, rule).inconclusive  # ~5% gap < 25% margin


def test_act_scales_winner_pauses_loser():
    FakeChannel.paused = []
    FakeChannel.budgets = []
    launched = launch_experiment(
        _experiment(), CREATIVES, channel_factory=lambda name, cfg: FakeChannel(name))
    from adsuite.experiment import Decision

    actions = act_on_decision(
        Decision(winner="A", loser="B", inconclusive=False, reason="x"),
        launched, channel_factory=lambda name, cfg: FakeChannel(name))
    assert any(v == "scaled" for v in actions.values())
    assert any(v == "paused" for v in actions.values())
    assert len(FakeChannel.budgets) == 2   # winner's two channels scaled
    assert len(FakeChannel.paused) == 2    # loser's two channels paused


# --- insights normalization ---
def test_normalize_meta_insights():
    data = {"data": [{"impressions": "1000", "inline_link_clicks": "40", "spend": "12.50",
                      "actions": [{"action_type": "purchase", "value": "3"}],
                      "action_values": [{"action_type": "purchase", "value": "75.0"}]}]}
    m = normalize_meta_insights(data)
    assert m.impressions == 1000 and m.clicks == 40 and m.spend == 12.5
    assert m.conversions == 3 and m.revenue == 75.0


def test_normalize_google_insights():
    data = [{"results": [{"metrics": {"impressions": "800", "clicks": "30",
                                      "costMicros": "9000000", "conversions": "4",
                                      "conversionsValue": "60"}}]}]
    m = normalize_google_insights(data)
    assert m.impressions == 800 and m.clicks == 30
    assert m.spend == 9.0 and m.conversions == 4 and m.revenue == 60.0
