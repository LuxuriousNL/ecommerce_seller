"""Core adsuite models: creatives, campaigns, metrics, experiments."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

ASPECT_RATIOS = ("1:1", "4:5", "9:16")  # feed, portrait, story/reel


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Creative(BaseModel):
    """A platform-ready creative: source images + copy for organic and paid use."""

    slug: str
    product_slug: str = ""
    image_paths: list[str] = Field(default_factory=list)
    image_urls: list[str] = Field(default_factory=list)
    aspect_ratios: list[str] = Field(default_factory=lambda: list(ASPECT_RATIOS))
    organic_caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    paid_headline: str = ""
    paid_primary_text: str = ""
    landing_url: str = ""


class Metrics(BaseModel):
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: int = 0
    revenue: float = 0.0

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions else 0.0

    @property
    def cpa(self) -> float:
        return self.spend / self.conversions if self.conversions else float("inf")

    @property
    def roas(self) -> float:
        return self.revenue / self.spend if self.spend else 0.0


class Ad(BaseModel):
    id: str | None = None
    creative_slug: str = ""
    channel: str = ""
    status: str = "draft"


class AdSet(BaseModel):
    id: str | None = None
    name: str = ""
    daily_budget: float = 5.0
    targeting: dict = Field(default_factory=dict)


class Campaign(BaseModel):
    id: str | None = None
    name: str
    channel: str          # meta_paid | google_ads
    objective: str = "traffic"
    status: str = "draft"  # draft | active | paused
    daily_budget: float = 5.0
    landing_url: str = ""
    metrics: Metrics = Field(default_factory=Metrics)


class ChannelResult(BaseModel):
    ok: bool = True
    ids: dict = Field(default_factory=dict)   # e.g. {campaign, adset, ad}
    dry_run: bool = False
    error: str | None = None


class PostResult(BaseModel):
    ok: bool = True
    post_id: str | None = None
    url: str = ""
    channel: str = ""
    dry_run: bool = False
    error: str | None = None


class ExperimentVariant(BaseModel):
    label: str
    product_slug: str
    creative_slug: str


class DecisionRule(BaseModel):
    metric: str = "cpa"          # cpa (lower wins) | roas/ctr (higher wins)
    min_spend: float = 20.0      # per variant before a call is allowed
    min_conversions: int = 5     # per variant before a call is allowed
    margin: float = 0.10         # winner must beat loser by this relative margin


class Experiment(BaseModel):
    slug: str
    variant_a: ExperimentVariant
    variant_b: ExperimentVariant
    channels: list[str] = Field(default_factory=lambda: ["meta_paid", "google_ads"])
    daily_budget: float = 10.0   # total, split across variants
    objective: str = "traffic"
    rule: DecisionRule = Field(default_factory=DecisionRule)
    status: str = "draft"        # draft | running | decided
