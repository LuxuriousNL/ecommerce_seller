"""Trend -> product concepts (Claude).

Turns a selected niche + micro-positioning into concrete, IP-safe product
concepts with design briefs, ready for the design/listing/pricing pipeline.
"""

from __future__ import annotations

import anthropic
from pydantic import BaseModel

from etsyshop.config import settings
from etsyshop.models import ProductConcept
from etsyshop.trends import TrendNiche

SYSTEM_PROMPT = """\
You are a print-on-demand product designer for an Etsy shop. Given a trending \
niche, you invent distinctive, commercially-strong product concepts a POD \
provider (Printify) can fulfill.

Hard rules:
- IP-SAFE ONLY. No brand names, logos, franchises, game/film characters, \
celebrity likenesses, sports marks, or "in the style of [living artist]". \
Original artwork only.
- Each concept must have a sharp micro-positioning (a specific buyer + angle), \
not a generic aesthetic. Differentiate within the niche.
- The design brief must be concrete enough to hand to an image model: subject, \
style/medium, palette, composition, and what to avoid.
- Match the product_type to the niche (e.g. ornaments, mugs, posters, tote \
bags). Keep it producible at 300 DPI with a clean transparent or print-ready \
design — no photo-realistic mockups baked into the art.
- slug: short, kebab-case, unique within the batch."""


class Concepts(BaseModel):
    concepts: list[ProductConcept]


def _user_prompt(niche: TrendNiche, count: int) -> str:
    return (
        f"Niche: {niche.name} ({niche.slug})\n"
        f"Why it's hot: {niche.why}\n"
        f"Product kind: {niche.kind}; suggested product: {niche.blueprint_hint or 'POD item'}\n"
        f"Seed keywords: {', '.join(niche.keywords)}\n"
        f"Micro-positioning angles to draw from: {', '.join(niche.micro_positioning)}\n"
        f"Typical price band: ${niche.price_low}-${niche.price_high}\n\n"
        f"Invent {count} distinct product concepts for this niche."
    )


def ideate(
    niche: TrendNiche,
    count: int = 3,
    *,
    client: anthropic.Anthropic | None = None,
) -> list[ProductConcept]:
    """Generate `count` product concepts for a niche."""
    settings.require("anthropic_api_key")
    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(niche, count)}],
        output_format=Concepts,
    )
    concepts = response.parsed_output.concepts
    for concept in concepts:
        concept.niche_slug = niche.slug  # ensure linkage regardless of model output
    return concepts
