"""Sync products to Shopify, reusing etsyshop listing copy.

Printify fulfills Shopify natively, so once a product exists the Printify <->
Shopify link handles production; this pushes the catalog + copy.
"""

from __future__ import annotations

from dataclasses import dataclass


def build_product_input(listing, *, product_type: str = "") -> dict:
    """Map an OptimizedListing-like (title/description/tags) to Shopify fields."""
    return {
        "title": listing.title,
        "description_html": f"<p>{listing.description}</p>",
        "product_type": product_type,
        "tags": list(getattr(listing, "tags", []) or []),
    }


@dataclass
class SyncResult:
    product_id: str | None = None
    handle: str = ""
    dry_run: bool = False
    error: str | None = None


def sync_product(client, listing, *, product_type: str = "", status: str = "DRAFT") -> SyncResult:
    """Create a Shopify product from an optimized listing."""
    try:
        fields = build_product_input(listing, product_type=product_type)
        product = client.create_product(status=status, **fields)
        return SyncResult(product_id=product.get("id"), handle=product.get("handle", ""),
                          dry_run=bool(product.get("dry_run")))
    except Exception as exc:  # noqa: BLE001
        return SyncResult(error=str(exc))
