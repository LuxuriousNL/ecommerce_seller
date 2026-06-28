"""Bridge trend signals into etsyshop's niche detector.

Decoupled: takes niche keyword data as plain input so trendscanner doesn't
import etsyshop. Maps signals onto existing niches and surfaces emerging terms
that match no niche yet (new-niche candidates).
"""

from __future__ import annotations

from trendscanner.models import TrendSignal


def index_niche_keywords(niches: list) -> dict[str, set[str]]:
    """Build {niche_slug: {keyword tokens}} from niche objects or dicts."""
    index: dict[str, set[str]] = {}
    for n in niches:
        slug = getattr(n, "slug", None) if not isinstance(n, dict) else n.get("slug")
        if not slug:
            continue
        name = (getattr(n, "name", "") if not isinstance(n, dict) else n.get("name", "")) or ""
        keywords = (getattr(n, "keywords", []) if not isinstance(n, dict)
                    else n.get("keywords", [])) or []
        kws: set[str] = set()
        for text in [name, *keywords]:
            t = str(text).lower()
            kws.add(t)
            kws.update(t.split())
        index[slug] = kws
    return index


def _terms_of(signal: TrendSignal) -> set[str]:
    t = signal.term.lower()
    return {t, *t.split()}


def match_signals(
    signals: list[TrendSignal], niche_keywords: dict[str, set[str]]
) -> dict[str, list[TrendSignal]]:
    """Group signals under the niches whose keywords they overlap."""
    out: dict[str, list[TrendSignal]] = {slug: [] for slug in niche_keywords}
    for sig in signals:
        terms = _terms_of(sig)
        for slug, kws in niche_keywords.items():
            if terms & kws:
                out[slug].append(sig)
    return {slug: sigs for slug, sigs in out.items() if sigs}


def emerging_signals(
    signals: list[TrendSignal], niche_keywords: dict[str, set[str]], *, top: int = 10
) -> list[TrendSignal]:
    """Signals matching no existing niche — candidate new niches, strongest first."""
    all_kw: set[str] = set().union(*niche_keywords.values()) if niche_keywords else set()
    unmatched = [s for s in signals if not (_terms_of(s) & all_kw)]
    unmatched.sort(key=lambda s: s.score, reverse=True)
    return unmatched[:top]
