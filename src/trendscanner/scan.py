"""Scan runner: fetch configured sources -> aggregate -> write a feed file.

Source fetching is injectable so the runner is testable without network. A
default JSON config maps source kinds to targets.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from trendscanner.aggregate import aggregate
from trendscanner.models import TrendSignal


@dataclass
class SourceConfig:
    kind: str       # rss | google_trends | ecommerce
    target: str     # url, or geo code for google_trends
    category: str = "other"


def _default_fetchers() -> dict[str, Callable[[SourceConfig], list[TrendSignal]]]:
    from trendscanner.sources.ecommerce import fetch_ecommerce
    from trendscanner.sources.google_trends import fetch_google_trends
    from trendscanner.sources.rss import fetch_rss

    return {
        "rss": lambda c: fetch_rss(c.target, category=c.category),
        "google_trends": lambda c: fetch_google_trends(c.target or "US", category=c.category),
        "ecommerce": lambda c: fetch_ecommerce(c.target, category=c.category),
    }


def run_sources(
    configs: list[SourceConfig],
    *,
    fetchers: dict[str, Callable[[SourceConfig], list[TrendSignal]]] | None = None,
) -> list[TrendSignal]:
    """Fetch every source, best-effort (a failing source is skipped, not fatal)."""
    fetchers = fetchers or _default_fetchers()
    signals: list[TrendSignal] = []
    for cfg in configs:
        fn = fetchers.get(cfg.kind)
        if not fn:
            continue
        try:
            signals.extend(fn(cfg))
        except Exception as exc:  # noqa: BLE001 — one bad source shouldn't sink the scan
            print(f"[trendscanner] source {cfg.kind}:{cfg.target} failed: {exc}", file=sys.stderr)
    return signals


def scan_to_feed(
    configs: list[SourceConfig],
    *,
    out_path: str | Path | None = None,
    min_count: int = 2,
    top: int = 30,
    fetchers=None,
) -> list[TrendSignal]:
    """Run sources, aggregate into ranked trends, optionally write a feed JSON."""
    raw = run_sources(configs, fetchers=fetchers)
    feed = aggregate(raw, top=top, min_count=min_count)
    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([s.model_dump() for s in feed], indent=2))
    return feed


def _load_configs(path: str) -> list[SourceConfig]:
    data = json.loads(Path(path).read_text())
    return [SourceConfig(**c) for c in data]


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: trendscan <sources.json> [out_feed.json]", file=sys.stderr)
        return 2
    configs = _load_configs(argv[0])
    out = argv[1] if len(argv) > 1 else "out/trend-feed.json"
    feed = scan_to_feed(configs, out_path=out)
    for s in feed[:20]:
        print(f"{s.score:>5.0f}  {s.category:<9} {s.term}")
    print(f"\n{len(feed)} trends -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
