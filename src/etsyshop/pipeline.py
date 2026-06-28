"""Phase 1: turn designs into Printify products (and publish to Etsy)."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from etsyshop.clients.printify import PrintifyClient
from etsyshop.models import Design, OptimizedListing, ProductTemplate


def build_product_payload(
    template: ProductTemplate,
    design: Design,
    image_id: str,
    listing: OptimizedListing | None = None,
) -> dict:
    """Assemble the Printify create-product body from a template + uploaded image.

    If `listing` (AI-optimized SEO) is provided it wins; otherwise we fall back to
    the design's title hint and the template defaults.
    """
    title = listing.title if listing else (design.title_hint or design.slug)
    tags = listing.tags if listing else template.default_tags
    description = listing.description if listing else template.description_prefix

    variants = [
        {"id": vid, "price": template.price_cents, "is_enabled": True}
        for vid in template.variant_ids
    ]

    placeholders = [
        {
            "position": p.position,
            "images": [
                {"id": image_id, "x": p.x, "y": p.y, "scale": p.scale, "angle": p.angle}
            ],
        }
        for p in template.placements
    ]
    print_areas = [{"variant_ids": template.variant_ids, "placeholders": placeholders}]

    return {
        "title": title,
        "description": description,
        "blueprint_id": template.blueprint_id,
        "print_provider_id": template.print_provider_id,
        "variants": variants,
        "print_areas": print_areas,
        "tags": tags[:13],
    }


def upload_design_image(client: PrintifyClient, design: Design) -> dict:
    """Upload a design's artwork to Printify, by URL or local file."""
    if design.image_url:
        return client.upload_image(f"{design.slug}.png", url=design.image_url)
    if design.image_path:
        path = Path(design.image_path)
        contents = base64.b64encode(path.read_bytes()).decode()
        return client.upload_image(path.name, contents_b64=contents)
    raise ValueError(f"Design '{design.slug}' has neither image_path nor image_url.")


@dataclass
class CreateResult:
    slug: str
    product_id: str | None
    published: bool
    error: str | None = None


def create_design_product(
    client: PrintifyClient,
    template: ProductTemplate,
    design: Design,
    *,
    listing: OptimizedListing | None = None,
    publish: bool = False,
) -> CreateResult:
    """Full single-design pipeline: upload -> create -> (optionally) publish."""
    try:
        image = upload_design_image(client, design)
        payload = build_product_payload(template, design, image["id"], listing)
        product = client.create_product(payload)
        product_id = str(product["id"])
        if publish:
            client.publish_product(product_id)
        return CreateResult(design.slug, product_id, published=publish)
    except Exception as exc:  # noqa: BLE001
        return CreateResult(design.slug, None, published=False, error=str(exc))
