"""Core trendscanner data model: a normalized trend signal."""

from __future__ import annotations

import datetime as dt
import re

from pydantic import BaseModel, Field

CATEGORIES = ("fashion", "gifting", "news", "ecommerce", "other")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class TrendSignal(BaseModel):
    """One observation that a term is trending, from one source."""

    source: str            # e.g. "rss:vogue", "google-trends"
    term: str
    category: str = "other"  # fashion | gifting | news | ecommerce | other
    score: float = 1.0       # source-relative strength
    url: str = ""
    observed_at: str = Field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def slug(self) -> str:
        return slugify(self.term)
