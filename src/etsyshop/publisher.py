"""Architecture B publisher: create and own the Etsy listing ourselves.

Printify remains the production + mockup backend; this creates the listing via
the Etsy API with full SEO control (category, all tags, attributes, materials,
alt text), relays Printify's rendered mockups (or uploads digital files), and
activates it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import httpx

from etsyshop.clients.etsy import EtsyClient
from etsyshop.models import ListingDraft, OptimizedListing, ProductTemplate
from etsyshop.taxonomy import map_attributes, resolve_taxonomy_id

FetchFn = Callable[[str], bytes]


def _default_fetch(url: str) -> bytes:
    resp = httpx.get(url, timeout=30.0)
    resp.raise_for_status()
    return resp.content


def draft_for_pod(
    template: ProductTemplate,
    image_urls: list[str],
    *,
    listing: OptimizedListing | None = None,
    shipping_profile_id: int | None = None,
) -> ListingDraft:
    """Assemble a physical-listing draft from a template + relayed mockup URLs."""
    title = listing.title if listing else template.name
    return ListingDraft(
        title=title,
        description=listing.description if listing else template.description_prefix,
        price=template.resolve_price_cents() / 100.0,
        listing_type="physical",
        tags=(listing.tags if listing else template.default_tags),
        materials=(listing.materials if listing else template.materials),
        taxonomy_query=template.etsy_taxonomy,
        attributes=template.etsy_attributes,
        shipping_profile_id=shipping_profile_id,
        alt_text=title,
        image_urls=image_urls,
    )


def draft_for_digital(
    listing: OptimizedListing,
    *,
    price: float,
    taxonomy_query: str | None,
    digital_files: list[str],
    image_paths: list[str] | None = None,
    attributes: dict[str, str] | None = None,
    when_made: str = "made_to_order",
) -> ListingDraft:
    """Assemble a digital download listing draft (no Printify, no fulfillment)."""
    return ListingDraft(
        title=listing.title,
        description=listing.description,
        price=price,
        quantity=999,
        listing_type="download",
        who_made="i_did",
        when_made=when_made,
        tags=listing.tags,
        materials=listing.materials,
        taxonomy_query=taxonomy_query,
        attributes=attributes or {},
        alt_text=listing.title,
        image_paths=image_paths or [],
        digital_files=digital_files,
    )


@dataclass
class PublishResult:
    listing_id: str | None = None
    state: str = "draft"
    images_uploaded: int = 0
    files_uploaded: int = 0
    taxonomy_id: int | None = None
    applied_attributes: list[str] = field(default_factory=list)
    skipped_attributes: list[str] = field(default_factory=list)
    error: str | None = None


def publish_listing(
    etsy: EtsyClient,
    draft: ListingDraft,
    *,
    shop_id: str | None = None,
    activate: bool = True,
    fetch: FetchFn = _default_fetch,
    auto_resolve_physical: bool = True,
) -> PublishResult:
    """Create an Etsy listing from a draft: category, listing, media, attributes, activate."""
    result = PublishResult()
    try:
        # 1. Category (required by createDraftListing).
        taxonomy_id = None
        if draft.taxonomy_query:
            match = resolve_taxonomy_id(etsy.get_seller_taxonomy_nodes(), draft.taxonomy_query)
            taxonomy_id = match.taxonomy_id if match else None
        if taxonomy_id is None:
            raise ValueError(f"Could not resolve Etsy category for '{draft.taxonomy_query}'.")
        result.taxonomy_id = taxonomy_id

        # 1b. Physical listings need a shipping profile (and a return policy) to
        # activate — resolve the shop's defaults if not supplied. Best-effort.
        shipping_id = draft.shipping_profile_id
        return_policy_id = None
        if draft.listing_type == "physical" and auto_resolve_physical:
            try:
                from etsyshop.shopconfig import (
                    resolve_return_policy_id,
                    resolve_shipping_profile_id,
                )

                shipping_id = shipping_id or resolve_shipping_profile_id(etsy, shop_id)
                return_policy_id = resolve_return_policy_id(etsy, shop_id)
            except Exception:  # noqa: BLE001 — proceed; activation will report if missing
                pass

        # 2. Create the draft listing.
        listing = etsy.create_draft_listing(
            title=draft.title,
            description=draft.description,
            price=draft.price,
            taxonomy_id=taxonomy_id,
            quantity=draft.quantity,
            who_made=draft.who_made,
            when_made=draft.when_made,
            listing_type=draft.listing_type,
            tags=draft.tags or None,
            materials=draft.materials or None,
            shipping_profile_id=shipping_id,
            return_policy_id=return_policy_id,
            is_personalizable=draft.is_personalizable or None,
            shop_id=shop_id,
        )
        listing_id = str(listing["listing_id"])
        result.listing_id = listing_id

        # 3a. Physical: relay Printify mockups (hero first via image order).
        rank = 0
        for url in draft.image_urls:
            rank += 1
            etsy.upload_listing_image(
                listing_id, fetch(url), rank=rank, alt_text=draft.alt_text, shop_id=shop_id
            )
            result.images_uploaded += 1

        # 3a'. Local preview images (e.g. the generated artwork for a digital product).
        for path in draft.image_paths:
            rank += 1
            p = Path(path)
            etsy.upload_listing_image(
                listing_id, p.read_bytes(), rank=rank, alt_text=draft.alt_text,
                filename=p.name, shop_id=shop_id,
            )
            result.images_uploaded += 1

        # 3b. Digital: upload download files.
        for rank, path in enumerate(draft.digital_files, start=1):
            p = Path(path)
            etsy.upload_listing_file(
                listing_id, p.read_bytes(), p.name, rank=rank, shop_id=shop_id
            )
            result.files_uploaded += 1

        # 4. Attributes (category-scoped; needs the taxonomy_id from step 1).
        if draft.attributes:
            props = etsy.get_taxonomy_properties(taxonomy_id).get("results") or []
            updates, skipped = map_attributes(props, draft.attributes)
            result.skipped_attributes = skipped
            for u in updates:
                etsy.update_listing_property(
                    listing_id, u.property_id, value_ids=u.value_ids,
                    values=u.values, shop_id=shop_id,
                )
                result.applied_attributes.append(f"{u.name}={u.values[0]}")

        # 5. Activate.
        if activate:
            etsy.activate_listing(listing_id, shop_id=shop_id)
            result.state = "active"
    except Exception as exc:  # noqa: BLE001
        result.error = str(exc)
    return result
