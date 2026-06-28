"""Enrich a published Etsy listing with the SEO fields Printify can't set.

After Printify publishes a product to Etsy it owns title/description/tags/price/
images, but leaves category and attributes unset — the fields Etsy's search
relies on most. This applies them via the Etsy API, which persists because
Printify never re-syncs them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from etsyshop.clients.etsy import EtsyClient
from etsyshop.clients.printify import PrintifyClient
from etsyshop.taxonomy import map_attributes, resolve_taxonomy_id


def etsy_listing_id_from_product(product: dict) -> str | None:
    """The Etsy listing id Printify records once a product is published."""
    for ext in product.get("external") or []:
        if ext.get("id"):
            return str(ext["id"])
    return None


def wait_for_etsy_listing_id(
    printify: PrintifyClient,
    product_id: str,
    *,
    attempts: int = 10,
    delay: float = 3.0,
) -> str | None:
    """Poll Printify until the async publish records the Etsy listing id."""
    for i in range(attempts):
        product = printify.get_product(product_id)
        listing_id = etsy_listing_id_from_product(product)
        if listing_id:
            return listing_id
        if i < attempts - 1:
            time.sleep(delay)
    return None


@dataclass
class EnrichReport:
    listing_id: str
    taxonomy_id: int | None = None
    taxonomy_path: str | None = None
    applied_attributes: list[str] = field(default_factory=list)
    skipped_attributes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    materials: list[str] = field(default_factory=list)
    error: str | None = None


def enrich_listing(
    etsy: EtsyClient,
    listing_id: str | int,
    *,
    taxonomy_query: str | None = None,
    tags: list[str] | None = None,
    materials: list[str] | None = None,
    attributes: dict[str, str] | None = None,
    shop_id: str | None = None,
) -> EnrichReport:
    """Apply category, tags, materials, and attributes to an existing listing."""
    report = EnrichReport(listing_id=str(listing_id))
    try:
        taxonomy_id: int | None = None
        if taxonomy_query:
            match = resolve_taxonomy_id(etsy.get_seller_taxonomy_nodes(), taxonomy_query)
            if match:
                taxonomy_id = match.taxonomy_id
                report.taxonomy_id = match.taxonomy_id
                report.taxonomy_path = match.full_path

        if taxonomy_id is not None or tags or materials:
            etsy.update_listing(
                listing_id, shop_id=shop_id,
                taxonomy_id=taxonomy_id, tags=tags, materials=materials,
            )
            report.tags = tags or []
            report.materials = materials or []

        # Attributes are category-scoped: we need a taxonomy_id to know valid values.
        if attributes and taxonomy_id is not None:
            props = etsy.get_taxonomy_properties(taxonomy_id).get("results") or []
            updates, skipped = map_attributes(props, attributes)
            report.skipped_attributes = skipped
            for u in updates:
                etsy.update_listing_property(
                    listing_id, u.property_id,
                    value_ids=u.value_ids, values=u.values, shop_id=shop_id,
                )
                report.applied_attributes.append(f"{u.name}={u.values[0]}")
        elif attributes:
            report.skipped_attributes = list(attributes)  # no category -> can't map
    except Exception as exc:  # noqa: BLE001
        report.error = str(exc)
    return report
