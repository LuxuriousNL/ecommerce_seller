"""trendscanner subproject tests."""

from __future__ import annotations

from trendscanner.models import TrendSignal, slugify


def test_slugify():
    assert slugify("Retro Pink Ghost!") == "retro-pink-ghost"
    assert slugify("  Cottagecore  Décor  ") == "cottagecore-d-cor"


def test_trend_signal_defaults_and_slug():
    sig = TrendSignal(source="rss:vogue", term="Coquette Bows", category="fashion", score=0.8)
    assert sig.slug == "coquette-bows"
    assert sig.category == "fashion"
    assert sig.observed_at  # auto-stamped
    assert sig.score == 0.8
