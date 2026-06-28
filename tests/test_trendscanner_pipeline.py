"""trendscanner pipeline tests: RSS parse -> aggregate -> bridge (offline)."""

from __future__ import annotations

from trendscanner.aggregate import aggregate, extract_terms
from trendscanner.bridge import emerging_signals, index_niche_keywords, match_signals
from trendscanner.models import TrendSignal
from trendscanner.sources.rss import parse_feed

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Gift Trends Weekly</title>
  <item><title>Coquette bows are everywhere this season</title>
        <link>https://example.com/a</link></item>
  <item><title>Personalised ornaments top the gift charts</title>
        <link>https://example.com/b</link></item>
  <item><title>Coquette bows on everything for autumn</title>
        <link>https://example.com/c</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Fashion Feed</title>
  <entry><title>Cottagecore decor returns</title><link href="https://x/1"/></entry>
</feed>"""


def test_parse_rss_skips_channel_title():
    sigs = parse_feed(RSS, source="rss:gifts", category="gifting")
    assert len(sigs) == 3  # items only, not the channel <title>
    assert sigs[0].category == "gifting" and sigs[0].url == "https://example.com/a"
    assert "Coquette bows" in sigs[0].term


def test_parse_atom():
    sigs = parse_feed(ATOM, source="rss:fashion", category="fashion")
    assert len(sigs) == 1 and sigs[0].term == "Cottagecore decor returns"
    assert sigs[0].url == "https://x/1"


def test_extract_terms_drops_stopwords_and_makes_ngrams():
    terms = extract_terms("Coquette bows are everywhere")
    assert "coquette" in terms
    assert "coquette bows" in terms
    assert "are" not in terms  # stopword


def test_aggregate_ranks_recurring_phrases():
    sigs = parse_feed(RSS, source="rss:gifts", category="gifting")
    agg = aggregate(sigs, min_count=2)
    terms = [s.term for s in agg]
    # "coquette bows" appears in two items -> should surface; one-off phrases drop.
    assert "coquette bows" in terms
    assert all(s.source == "aggregate" and s.score >= 2 for s in agg)


def test_bridge_matches_and_finds_emerging():
    niches = [
        {"slug": "personalised-ornaments", "name": "Personalised ornaments",
         "keywords": ["custom name ornament", "family ornament"]},
        {"slug": "halloween-svg", "name": "Halloween SVGs", "keywords": ["ghost svg"]},
    ]
    idx = index_niche_keywords(niches)
    signals = [
        TrendSignal(source="aggregate", term="personalised ornaments", category="gifting", score=3),
        TrendSignal(source="aggregate", term="coquette bows", category="fashion", score=5),
    ]
    matched = match_signals(signals, idx)
    assert "personalised-ornaments" in matched
    assert "halloween-svg" not in matched  # no overlap

    emerging = emerging_signals(signals, idx)
    assert [s.term for s in emerging] == ["coquette bows"]  # unmatched, highest score
