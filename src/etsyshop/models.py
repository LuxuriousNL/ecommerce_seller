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

    @classmethod
    def load(cls, path: str | Path) -> "ProductTemplate":
        return cls.model_validate_json(Path(path).read_text())


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
