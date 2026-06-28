"""Google Trends adapter via the official daily-trends RSS endpoint.

Uses Google's published RSS feed (not HTML scraping). Each <item> title is a
trending search term.
"""

from __future__ import annotations

from trendscanner.models import TrendSignal
from trendscanner.net import DEFAULT_UA, polite_get
from trendscanner.sources.rss import parse_feed

DAILY_RSS = "https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}"


def parse_google_trends(xml: bytes | str, *, geo: str = "US",
                        category: str = "news") -> list[TrendSignal]:
    return parse_feed(xml, source=f"google-trends:{geo}", category=category)


def fetch_google_trends(geo: str = "US", *, category: str = "news",
                        user_agent: str = DEFAULT_UA) -> list[TrendSignal]:
    raw = polite_get(DAILY_RSS.format(geo=geo), user_agent=user_agent)
    return parse_google_trends(raw, geo=geo, category=category)
