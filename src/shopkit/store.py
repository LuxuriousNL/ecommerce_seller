"""Registry of niche stores (git-ignored state) + honest go-live guidance.

Billable Shopify store creation is not a public API. We record stores (Partner
dev stores or manually-created production stores) and operate them via the Admin
API; production go-live is a documented manual step.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_STORE = Path(".state/shops.json")

GO_LIVE_CHECKLIST = [
    "Create the store (Partner dev store, or a paid production store in Shopify admin).",
    "Generate an Admin API access token and set SHOPIFY_SHOP_DOMAIN/SHOPIFY_ADMIN_TOKEN.",
    "Run `shopctl provision --niche <slug>` to build the collection + brand.",
    "Sync products, then `shopctl feed` and install the Meta/Google pixel.",
    "Point adsuite paid campaigns at the store URL; submit the feed to Merchant Center.",
]


class ShopRecord(BaseModel):
    niche_slug: str
    domain: str = ""
    collection_id: str | None = None
    pixel_id: str | None = None
    status: str = "pending"  # pending | live
    created_at: str = Field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))


def load_shops(path: str | Path = DEFAULT_STORE) -> dict[str, ShopRecord]:
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return {k: ShopRecord.model_validate(v) for k, v in data.items()}


def save_shop(record: ShopRecord, path: str | Path = DEFAULT_STORE) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    shops = load_shops(path)
    shops[record.niche_slug] = record
    p.write_text(json.dumps({k: v.model_dump() for k, v in shops.items()}, indent=2))


def register_store(niche_slug: str, *, domain: str = "", path: str | Path = DEFAULT_STORE) -> ShopRecord:
    """Record intent to create a store for a niche (status pending until go-live)."""
    rec = ShopRecord(niche_slug=niche_slug, domain=domain,
                     status="live" if domain else "pending")
    save_shop(rec, path)
    return rec
