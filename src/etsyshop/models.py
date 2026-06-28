"""Domain models: product templates, design inputs, optimized listings."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class ImagePlacement(BaseModel):
    """Where a design sits within a print area (Printify coords are 0..1)."""

    position: str = "front"  # e.g. front, back
    x: float = 0.5
    y: float = 0.5
    scale: float = 1.0
    angle: int = 0


class ProductTemplate(BaseModel):
    """A reusable recipe for one product type.

    blueprint_id / print_provider_id / variant_ids come from Printify's catalog.
    Discover them with `etsyshop catalog ...` commands.
    """

    name: str
    blueprint_id: int
    print_provider_id: int
    variant_ids: list[int] = Field(default_factory=list)
    price_cents: int = 1999
    placements: list[ImagePlacement] = Field(default_factory=lambda: [ImagePlacement()])
    default_tags: list[str] = Field(default_factory=list)
    description_prefix: str = ""
    # Optional: when both are set, the price is computed by the fee-aware engine.
    product_cost: float | None = None
    target_margin: float | None = None
    fee_country: str = "US"

    @classmethod
    def load(cls, path: str | Path) -> "ProductTemplate":
        return cls.model_validate_json(Path(path).read_text())

    def resolve_price_cents(self) -> int:
        """Computed price when product_cost + target_margin are set; else the constant."""
        if self.product_cost is not None and self.target_margin is not None:
            from etsyshop.pricing import SCHEDULES, US, CostInputs, recommend_price

            fees = SCHEDULES.get(self.fee_country, US)
            rec = recommend_price(
                CostInputs(product_cost=self.product_cost),
                fees,
                target_margin=self.target_margin,
            )
            return round(rec.list_price * 100)
        return self.price_cents


class Design(BaseModel):
    """One artwork to turn into a product, plus hints for the AI optimizer."""

    slug: str
    image_path: str | None = None
    image_url: str | None = None
    title_hint: str = ""
    theme: str = ""
    keywords: list[str] = Field(default_factory=list)
    niche: str = ""


class DesignManifest(BaseModel):
    designs: list[Design]

    @classmethod
    def load(cls, path: str | Path) -> "DesignManifest":
        data = json.loads(Path(path).read_text())
        if isinstance(data, list):
            data = {"designs": data}
        return cls.model_validate(data)


class DesignBrief(BaseModel):
    """Structured brief for an image model (Subject+Style+Context, report 2)."""

    subject: str
    style: str
    palette: str
    composition: str = ""
    must_include: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    aspect_ratio: str = "4:5"

    def to_prompt(self) -> str:
        lines = [
            f"Subject: {self.subject}",
            f"Style/medium: {self.style}",
            f"Palette: {self.palette}",
        ]
        if self.composition:
            lines.append(f"Composition: {self.composition}")
        if self.must_include:
            lines.append(f"Must include: {', '.join(self.must_include)}")
        avoid = list(self.avoid) + ["text", "watermark", "logo", "signature"]
        lines.append(f"Avoid: {', '.join(dict.fromkeys(avoid))}")
        lines.append(f"Aspect ratio: {self.aspect_ratio}")
        return "\n".join(lines)


class ProductConcept(BaseModel):
    """A trend-derived idea ready to flow through design -> listing -> pricing."""

    slug: str
    product_type: str
    niche_slug: str
    micro_positioning: str = ""
    title_hint: str = ""
    seed_keywords: list[str] = Field(default_factory=list)
    design: DesignBrief

    def to_design(self) -> "Design":
        theme = f"{self.design.subject}; {self.design.style}".strip("; ")
        return Design(
            slug=self.slug,
            title_hint=self.title_hint,
            theme=theme,
            niche=self.micro_positioning,
            keywords=self.seed_keywords,
        )


class OptimizedListing(BaseModel):
    """SEO output from the Phase 2 optimizer.

    Etsy field limits (title <=140 chars, <=13 tags of <=20 chars each, <=13
    materials) are enforced by `optimize.normalize_listing`, not as hard schema
    constraints, so a slightly oversized model response is trimmed rather than
    rejected.
    """

    title: str
    tags: list[str] = Field(default_factory=list)
    description: str
    materials: list[str] = Field(default_factory=list)
