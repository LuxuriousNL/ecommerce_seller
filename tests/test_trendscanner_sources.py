"""Google Trends + ecommerce source tests and the scan runner (offline)."""

from __future__ import annotations

from trendscanner.models import TrendSignal
from trendscanner.scan import SourceConfig, run_sources, scan_to_feed
from trendscanner.sources.ecommerce import parse_jsonld_products
from trendscanner.sources.google_trends import parse_google_trends

GTRENDS_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Daily Search Trends</title>
  <item><title>pumpkin spice latte</title></item>
  <item><title>halloween costumes 2026</title></item>
</channel></rss>"""

PRODUCT_HTML = """<html><head>
<script type="application/ld+json">
{"@type":"Product","name":"Coquette Bow Hair Clip"}
</script>
<script type="application/ld+json">
{"@type":"ItemList","itemListElement":[
  {"item":{"@type":"Product","name":"Retro Sunset Tee"}},
  {"item":{"@type":"Product","name":"Coquette Bow Hair Clip"}}
]}
</script>
</head><body>...</body></html>"""


def test_parse_google_trends():
    sigs = parse_google_trends(GTRENDS_RSS, geo="US", category="news")
    assert [s.term for s in sigs] == ["pumpkin spice latte", "halloween costumes 2026"]
    assert all(s.source == "google-trends:US" for s in sigs)


def test_parse_jsonld_products_dedupes():
    sigs = parse_jsonld_products(PRODUCT_HTML, source="ecom:test")
    terms = [s.term for s in sigs]
    assert "Coquette Bow Hair Clip" in terms
    assert "Retro Sunset Tee" in terms
    assert len(terms) == len(set(terms))  # deduped across the two scripts
    assert all(s.category == "ecommerce" for s in sigs)


def test_run_sources_is_best_effort(capsys):
    def good(cfg):
        return [TrendSignal(source="x", term="coquette bows", category=cfg.category)]

    def boom(cfg):
        raise RuntimeError("network down")

    configs = [SourceConfig("rss", "u1", "fashion"), SourceConfig("ecommerce", "u2")]
    signals = run_sources(configs, fetchers={"rss": good, "ecommerce": boom})
    assert len(signals) == 1 and signals[0].term == "coquette bows"
    assert "failed" in capsys.readouterr().err  # the bad source was logged, not raised


def test_scan_to_feed_writes_file(tmp_path):
    def fetch(cfg):
        return [
            TrendSignal(source="s", term="coquette bows", category="fashion"),
            TrendSignal(source="s", term="coquette bows everywhere", category="fashion"),
        ]

    out = tmp_path / "feed.json"
    feed = scan_to_feed([SourceConfig("rss", "u", "fashion")],
                        out_path=out, min_count=2, fetchers={"rss": fetch})
    assert out.exists()
    assert any(s.term == "coquette bows" for s in feed)
