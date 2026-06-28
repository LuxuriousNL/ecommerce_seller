"""RSS/Atom source adapter — the preferred, ToS-friendly trend source."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from trendscanner.models import TrendSignal
from trendscanner.net import DEFAULT_UA, polite_get


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def parse_feed(xml: bytes | str, *, source: str, category: str = "news") -> list[TrendSignal]:
    """Parse RSS <item><title> and Atom <entry><title> into signals (pure)."""
    root = ET.fromstring(xml if isinstance(xml, (bytes, str)) else str(xml))
    signals: list[TrendSignal] = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        title = next(
            (c.text.strip() for c in node if _local(c.tag) == "title" and c.text), None
        )
        link = next(
            (c.get("href") or (c.text or "") for c in node if _local(c.tag) == "link"), ""
        )
        if title:
            signals.append(TrendSignal(source=source, term=title, category=category, url=link))
    return signals


def fetch_rss(
    url: str,
    *,
    source: str | None = None,
    category: str = "news",
    user_agent: str = DEFAULT_UA,
) -> list[TrendSignal]:
    """Fetch a feed (robots-aware) and parse it into signals."""
    raw = polite_get(url, user_agent=user_agent)
    return parse_feed(raw, source=source or f"rss:{url}", category=category)
