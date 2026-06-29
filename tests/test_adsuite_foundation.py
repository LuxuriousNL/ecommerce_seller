"""Epic A1: adsuite models, config, creative builder."""

from __future__ import annotations

from types import SimpleNamespace

from adsuite.config import AdSettings, channel_available
from adsuite.creative import CopyOutput, build_copy, build_creative, ensure_disclosure
from adsuite.models import Experiment, ExperimentVariant, Metrics, slugify


# --- models ---
def test_slugify():
    assert slugify("Retro Sunset Tee!") == "retro-sunset-tee"


def test_metrics_derived():
    m = Metrics(impressions=1000, clicks=50, spend=20.0, conversions=4, revenue=100.0)
    assert m.ctr == 0.05
    assert m.cpa == 5.0
    assert m.roas == 5.0
    assert Metrics().cpa == float("inf")  # no conversions
    assert Metrics().ctr == 0.0


def test_experiment_holds_two_variants():
    exp = Experiment(
        slug="tee-vs-mug",
        variant_a=ExperimentVariant(label="A", product_slug="tee", creative_slug="tee-c"),
        variant_b=ExperimentVariant(label="B", product_slug="mug", creative_slug="mug-c"),
    )
    assert exp.variant_a.label != exp.variant_b.label
    assert exp.channels == ["meta_paid", "google_ads"]
    assert exp.rule.metric == "cpa"


# --- config ---
def test_channel_available():
    cfg = AdSettings(META_ACCESS_TOKEN="t", META_PAGE_ID="p")
    assert channel_available("meta_organic", cfg)
    assert not channel_available("meta_paid", cfg)        # needs ad account
    assert not channel_available("google_ads", cfg)
    assert not channel_available("nonsense", cfg)


# --- creative ---
def test_ensure_disclosure_idempotent():
    assert ensure_disclosure("Shop now").startswith("Ad.")
    assert ensure_disclosure("Ad. Shop now") == "Ad. Shop now"
    assert ensure_disclosure("Sponsored: shop now") == "Sponsored: shop now"


class FakeAnthropic:
    def __init__(self, copy):
        self._copy = copy

    @property
    def messages(self):
        c = self

        class M:
            def parse(self, **kw):
                c.captured = kw
                return SimpleNamespace(parsed_output=c._copy)
        return M()


def test_build_copy_and_creative(monkeypatch):
    from adsuite import creative as creative_mod
    monkeypatch.setattr(creative_mod.settings, "anthropic_api_key", "test")
    copy = CopyOutput(
        organic_caption="Catch the wave.",
        hashtags=["#retro", "surf"],
        paid_headline="Retro Surf Tee",
        paid_primary_text="Shop the retro sunset tee.",
    )
    out = build_copy("retro sunset surf tee", client=FakeAnthropic(copy))
    assert out.paid_headline == "Retro Surf Tee"

    cr = build_creative("retro-tee", product_slug="retro-tee",
                        image_paths=["designs/art/retro.png"],
                        landing_url="https://etsy.com/listing/1", copy=out)
    assert cr.organic_caption == "Catch the wave."
    assert cr.hashtags == ["retro", "surf"]              # '#' stripped
    assert cr.paid_primary_text.startswith("Ad.")        # disclosure added
    assert "1:1" in cr.aspect_ratios and "9:16" in cr.aspect_ratios
    assert cr.landing_url.endswith("/listing/1")
