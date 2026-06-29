"""Build Etsy listing inventory (variations) from Printify variants.

Each Etsy offering carries the Printify variant id as its SKU, so an incoming
order routes straight to the right variant for production — independent of the
product_ids Etsy assigns.
"""

from __future__ import annotations


def build_inventory(
    variants: list[dict],
    *,
    property_id: int | None = None,
    property_name: str | None = None,
) -> list[dict]:
    """variants: [{variant_id, price, quantity?, is_enabled?, option?}] -> Etsy products.

    `price` is in the listing currency (float). If `property_id`/`property_name`
    and per-variant `option` are given, each variation gets that attribute value
    (e.g. Size=Large).
    """
    products: list[dict] = []
    for v in variants:
        offering = {
            "price": v["price"],
            "quantity": v.get("quantity", 999),
            "is_enabled": v.get("is_enabled", True),
        }
        product: dict = {"sku": str(v["variant_id"]), "offerings": [offering]}
        if property_id and property_name and v.get("option"):
            product["property_values"] = [{
                "property_id": property_id,
                "property_name": property_name,
                "values": [v["option"]],
            }]
        products.append(product)
    return products
