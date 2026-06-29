"""Manual fulfillment bridge for Architecture B.

We own the Etsy listing, so Printify doesn't auto-fulfill. This turns an Etsy
order (receipt) into a Printify production order, using the listing->product
map. Deferred-but-present: run it by hand for the first orders; automate the
poll loop once volume justifies it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from etsyshop.clients.printify import PrintifyClient
from etsyshop.store import ListingRecord


def _split_name(full: str) -> tuple[str, str]:
    parts = (full or "").strip().split(maxsplit=1)
    if not parts:
        return "", ""
    return (parts[0], parts[1] if len(parts) > 1 else "")


def build_printify_order(record: ListingRecord, receipt: dict) -> dict:
    """Build a Printify create-order payload for one listing within a receipt."""
    line_items = []
    for txn in receipt.get("transactions") or []:
        if str(txn.get("listing_id")) != record.etsy_listing_id:
            continue
        # Prefer the SKU (set to the Printify variant id at publish), then the
        # explicit variant_map, then the listing's default variant.
        sku = txn.get("sku")
        variant_id = int(sku) if sku is not None and str(sku).isdigit() else None
        if variant_id is None:
            variant_id = (
                record.variant_map.get(str(txn.get("product_id")))
                or record.default_variant_id
            )
        line_items.append(
            {
                "product_id": record.printify_product_id,
                "variant_id": variant_id,
                "quantity": txn.get("quantity", 1),
            }
        )
    first, last = _split_name(receipt.get("name", ""))
    return {
        "external_id": f"etsy-{receipt.get('receipt_id')}",
        "label": str(receipt.get("receipt_id", "")),
        "line_items": line_items,
        "shipping_method": 1,
        "send_shipping_notification": False,
        "address_to": {
            "first_name": first,
            "last_name": last,
            "email": receipt.get("buyer_email", ""),
            "country": receipt.get("country_iso", ""),
            "region": receipt.get("state", ""),
            "address1": receipt.get("first_line", ""),
            "address2": receipt.get("second_line", "") or "",
            "city": receipt.get("city", ""),
            "zip": receipt.get("zip", ""),
        },
    }


@dataclass
class FulfillResult:
    receipt_id: str
    orders_created: list[str] = field(default_factory=list)
    skipped_listings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def fulfill_receipt(
    printify: PrintifyClient,
    records: dict[str, ListingRecord],
    receipt: dict,
    *,
    send_to_production: bool = False,
) -> FulfillResult:
    """Create Printify orders for every mapped listing in an Etsy receipt."""
    result = FulfillResult(receipt_id=str(receipt.get("receipt_id")))
    listing_ids = {str(t.get("listing_id")) for t in receipt.get("transactions") or []}
    for listing_id in listing_ids:
        record = records.get(listing_id)
        if not record or not record.printify_product_id:
            result.skipped_listings.append(listing_id)
            continue
        payload = build_printify_order(record, receipt)
        if not payload["line_items"]:
            result.skipped_listings.append(listing_id)
            continue
        try:
            order = printify.create_order(payload)
            order_id = str(order.get("id", ""))
            result.orders_created.append(order_id)
            if send_to_production and order_id:
                printify.send_to_production(order_id)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"{listing_id}: {exc}")
    return result
