"""Trend catalog + seasonal selector tests."""

from __future__ import annotations

import datetime as dt

from etsyshop.trends import load_trends, trending_now


def test_catalog_loads():
    niches = load_trends()
    assert len(niches) >= 12
    slugs = {n.slug for n in niches}
    assert "personalised-ornaments" in slugs and "halloween-svg" in slugs


def test_status_peak_build_upcoming_off():
    ornaments = next(n for n in load_trends() if n.slug == "personalised-ornaments")
    assert ornaments.status(12) == "peak"      # December
    assert ornaments.status(9) == "build"      # September (in window, not peak)
    assert ornaments.status(8) == "upcoming"   # opens next month
    assert ornaments.status(6) == "off"        # too far out


def test_june_surfaces_july_launch_niches():
    """At the current date (late June 2026) the engine should flag July items."""
    scored = trending_now(on=dt.date(2026, 6, 28))
    slugs = [s.niche.slug for s in scored]
    assert "teacher-gifts" in slugs
    assert "dorm-decor" in slugs
    assert "halloween-svg" in slugs
    # December-only niches are not yet actionable in June.
    assert "printable-gift-tags" not in slugs
    assert all(s.status == "upcoming" for s in scored)


def test_peak_ranks_above_build_and_upcoming():
    scored = trending_now(month=10)  # October — several niches at peak
    scores = [s.score for s in scored]
    assert scores == sorted(scores, reverse=True)
    assert scored[0].status == "peak"


def test_printify_only_filters_to_pod():
    scored = trending_now(month=10, printify_only=True)
    assert scored, "expected some POD niches in October"
    assert all(s.niche.printify_fit for s in scored)
    assert all(s.niche.kind == "pod" or s.niche.printify_fit for s in scored)


def test_kind_filter():
    digital = trending_now(month=11, kind="digital")
    assert all(s.niche.kind == "digital" for s in digital)
