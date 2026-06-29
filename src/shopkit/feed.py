"""Google Merchant Center product feed (unlocks Shopping / Performance Max).

Generates the standard tab-separated Google product feed so a Shopify store's
catalog can be advertised via Google Shopping / PMax — the channel Etsy-only
sellers can't use.
"""

from __future__ import annotations

from pathlib import Path

COLUMNS = [
    "id", "title", "description", "link", "image_link",
    "availability", "price", "condition", "brand",
]


def _row(product: dict, currency: str) -> list[str]:
    price = product.get("price", 0.0)
    return [
        str(product.get("id", "")),
        str(product.get("title", "")),
        str(product.get("description", "")).replace("\t", " ").replace("\n", " "),
        str(product.get("link", "")),
        str(product.get("image_link", "")),
        product.get("availability", "in stock"),
        f"{float(price):.2f} {currency}",
        product.get("condition", "new"),
        str(product.get("brand", "")),
    ]


def build_feed(products: list[dict], *, currency: str = "USD") -> str:
    """Build a Google Merchant tab-separated feed (header + one row per product)."""
    lines = ["\t".join(COLUMNS)]
    for p in products:
        lines.append("\t".join(_row(p, currency)))
    return "\n".join(lines) + "\n"


def write_feed(products: list[dict], path: str | Path, *, currency: str = "USD") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_feed(products, currency=currency))
    return p
