"""Bridge between adsuite and etsyshop.

Sources creatives from published Etsy listings (the etsyshop store) and turns an
experiment outcome into a signal the product planner can act on (double down on
the winning product).
"""

from __future__ import annotations

from adsuite.creative import CopyOutput, build_creative
from adsuite.models import Creative
from adsuite.store import ExperimentRecord

ETSY_LISTING_URL = "https://www.etsy.com/listing/{listing_id}"


def creative_from_listing(
    listing_record,
    *,
    image_urls: list[str] | None = None,
    image_paths: list[str] | None = None,
    copy: CopyOutput | None = None,
) -> Creative:
    """Build an ad Creative from an etsyshop ListingRecord (duck-typed)."""
    listing_id = getattr(listing_record, "etsy_listing_id", "")
    slug = getattr(listing_record, "slug", "") or f"listing-{listing_id}"
    return build_creative(
        slug,
        product_slug=slug,
        image_urls=image_urls or [],
        image_paths=image_paths or [],
        landing_url=ETSY_LISTING_URL.format(listing_id=listing_id) if listing_id else "",
        copy=copy,
    )


def winner_signal(record: ExperimentRecord) -> dict | None:
    """Turn a decided experiment into a 'double down on this product' signal."""
    if record.status != "decided" or not record.winner:
        return None
    products = {"A": record.variant_a_product, "B": record.variant_b_product}
    return {
        "experiment": record.slug,
        "winning_product": products.get(record.winner, ""),
        "losing_product": products.get("B" if record.winner == "A" else "A", ""),
        "action": "scale",
    }
