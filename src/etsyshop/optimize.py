"""Phase 2: AI listing optimization with Claude.

Generates Etsy-compliant SEO (title, 13 tags, description, materials) for a
design, using the Anthropic Python SDK with structured outputs.
"""

from __future__ import annotations

import re

import anthropic

from etsyshop.config import settings
from etsyshop.models import Design, OptimizedListing, ProductTemplate

SYSTEM_PROMPT = """\
You are an expert Etsy SEO strategist for a print-on-demand shop. You write \
listings that rank in Etsy search and convert browsers into buyers.

Follow Etsy's hard rules exactly:
- title: <=140 characters. Lead with the most-searched keyword phrase. Readable, \
not keyword-stuffed. No ALL CAPS, no emoji.
- tags: EXACTLY 13 tags. Each tag <=20 characters. Multi-word long-tail phrases \
(e.g. "retro sunset shirt"), lowercase, no punctuation, no duplicates, no single \
words that already appear as another tag's substring. Mix broad and niche.
- description: 2-4 short paragraphs. Open with a compelling hook that repeats the \
primary keyword, then product details, then a light call to action. Plain text.
- materials: up to 13 short material/keyword terms relevant to the product.

Base every choice on the design theme, the buyer's likely search intent, and the \
product type. Do not invent product specs you weren't given."""


def _build_user_prompt(design: Design, template: ProductTemplate) -> str:
    parts = [
        f"Product type: {template.name}",
        f"Design slug: {design.slug}",
    ]
    if design.title_hint:
        parts.append(f"Working title / idea: {design.title_hint}")
    if design.theme:
        parts.append(f"Theme: {design.theme}")
    if design.niche:
        parts.append(f"Target niche / audience: {design.niche}")
    if design.keywords:
        parts.append(f"Seed keywords: {', '.join(design.keywords)}")
    parts.append("\nWrite the optimized Etsy listing for this product.")
    return "\n".join(parts)


def _clean_tag(tag: str) -> str:
    tag = re.sub(r"[^a-z0-9 ]", "", tag.lower()).strip()
    return re.sub(r"\s+", " ", tag)


def normalize_listing(listing: OptimizedListing) -> OptimizedListing:
    """Enforce Etsy's hard limits on a raw model response."""
    title = listing.title.strip()[:140]

    seen: set[str] = set()
    tags: list[str] = []
    for raw in listing.tags:
        tag = _clean_tag(raw)[:20].strip()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    tags = tags[:13]

    materials = [m.strip()[:45] for m in listing.materials if m.strip()][:13]

    return OptimizedListing(
        title=title, tags=tags, description=listing.description.strip(), materials=materials
    )


def optimize_listing(
    design: Design,
    template: ProductTemplate,
    *,
    client: anthropic.Anthropic | None = None,
) -> OptimizedListing:
    """Generate an Etsy-optimized listing for a single design."""
    settings.require("anthropic_api_key")
    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(design, template)}],
        output_format=OptimizedListing,
    )
    return normalize_listing(response.parsed_output)
