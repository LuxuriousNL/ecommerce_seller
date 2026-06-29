"""CreativeBuilder: design/mockup + product context -> platform copy & creative.

Claude writes the organic caption (+ hashtags) and paid ad copy; paid copy
carries an FTC/ASA ad disclosure. Pure assembly otherwise.
"""

from __future__ import annotations

import anthropic
from pydantic import BaseModel, Field

from adsuite.config import settings
from adsuite.models import ASPECT_RATIOS, Creative

SYSTEM_PROMPT = """\
You are a social + performance-marketing copywriter for an Etsy print-on-demand \
shop. Write concise, on-brand, platform-aware copy that drives clicks without \
hype or prohibited claims (no guarantees, no medical/financial claims).

Produce:
- organic_caption: 1-3 sentences for Instagram/Facebook/TikTok, warm and specific.
- hashtags: 8-15 relevant, lowercase, no '#'.
- paid_headline: <=40 chars, benefit-led.
- paid_primary_text: 1-2 sentences for a paid ad; clear CTA to shop the listing.

Keep it truthful and specific to the product; do not invent specs."""


class CopyOutput(BaseModel):
    organic_caption: str
    hashtags: list[str] = Field(default_factory=list)
    paid_headline: str
    paid_primary_text: str


def build_copy(
    product_context: str,
    *,
    client: anthropic.Anthropic | None = None,
) -> CopyOutput:
    """Generate organic + paid copy for a product."""
    settings.require("anthropic_api_key")
    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Product: {product_context}\n\nWrite the copy."}],
        output_format=CopyOutput,
    )
    return response.parsed_output


AD_DISCLOSURE = "Ad."


def ensure_disclosure(text: str) -> str:
    """FTC/ASA: paid copy must be identifiable as an ad."""
    low = text.lower()
    if low.startswith("ad") or "#ad" in low or "sponsored" in low:
        return text
    return f"{AD_DISCLOSURE} {text}".strip()


def build_creative(
    slug: str,
    *,
    product_slug: str = "",
    image_paths: list[str] | None = None,
    image_urls: list[str] | None = None,
    landing_url: str = "",
    copy: CopyOutput | None = None,
    aspect_ratios: list[str] | None = None,
) -> Creative:
    """Assemble a Creative from sources + (optional) generated copy."""
    hashtags = copy.hashtags if copy else []
    return Creative(
        slug=slug,
        product_slug=product_slug,
        image_paths=image_paths or [],
        image_urls=image_urls or [],
        aspect_ratios=aspect_ratios or list(ASPECT_RATIOS),
        organic_caption=copy.organic_caption if copy else "",
        hashtags=[h.lstrip("#") for h in hashtags],
        paid_headline=copy.paid_headline if copy else "",
        paid_primary_text=ensure_disclosure(copy.paid_primary_text) if copy else "",
        landing_url=landing_url,
    )
