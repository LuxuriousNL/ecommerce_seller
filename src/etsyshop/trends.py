"""Trend catalog + date-aware selector.

Encodes the ranked, seasonal Etsy niches from the research and answers the
operational question: "what should I be creating right now?" — by scoring each
niche against the current month (peak > build > upcoming).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from pydantic import BaseModel, Field

# data/trends.json lives at the repo root, two levels up from this file's package.
_DATA = Path(__file__).resolve().parents[2] / "data" / "trends.json"

SCORE = {"peak": 3, "build": 2, "upcoming": 1, "off": 0}


class TrendNiche(BaseModel):
    slug: str
    rank: int
    name: str
    demand: str
    competition: str
    margin_low: float
    margin_high: float
    complexity: str
    kind: str  # pod | digital | physical
    printify_fit: bool
    blueprint_hint: str | None = None
    price_low: float
    price_high: float
    window: list[int]
    peak: list[int]
    keywords: list[str] = Field(default_factory=list)
    micro_positioning: list[str] = Field(default_factory=list)
    why: str = ""

    def status(self, month: int) -> str:
        """peak / build / upcoming / off for the given month (1-12)."""
        if month in self.peak:
            return "peak"
        if month in self.window:
            return "build"
        # "upcoming" if the window opens within the next 1-2 months (year-wrapping).
        if any(((m - month) % 12) in (1, 2) for m in self.window):
            return "upcoming"
        return "off"

    def score(self, month: int) -> int:
        return SCORE[self.status(month)]


class ScoredNiche(BaseModel):
    niche: TrendNiche
    status: str
    score: int


def load_trends(path: str | Path | None = None) -> list[TrendNiche]:
    data = json.loads(Path(path or _DATA).read_text())
    return [TrendNiche.model_validate(n) for n in data["niches"]]


def trending_now(
    month: int | None = None,
    *,
    on: dt.date | None = None,
    printify_only: bool = False,
    kind: str | None = None,
    niches: list[TrendNiche] | None = None,
) -> list[ScoredNiche]:
    """Niches worth acting on now, best first.

    Ordered by season score (peak first), then catalog rank. `printify_only`
    keeps POD-fulfillable niches; `kind` filters digital/physical/pod.
    """
    if month is None:
        month = (on or dt.date.today()).month
    catalog = niches if niches is not None else load_trends()

    out: list[ScoredNiche] = []
    for n in catalog:
        if printify_only and not n.printify_fit:
            continue
        if kind and n.kind != kind:
            continue
        score = n.score(month)
        if score <= 0:
            continue
        out.append(ScoredNiche(niche=n, status=n.status(month), score=score))

    out.sort(key=lambda s: (-s.score, s.niche.rank))
    return out
