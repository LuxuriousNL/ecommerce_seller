"""Persistent map of Etsy listings we own -> their Printify product/variants.

Architecture B decouples the listing (ours) from production (Printify), so we
must remember the link to route an order back to production. Stored as JSON in
a local state file (git-ignored).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_STORE = Path(".state/listings.json")


class ListingRecord(BaseModel):
    etsy_listing_id: str
    slug: str = ""
    kind: str = "physical"  # physical | download
    printify_product_id: str | None = None
    default_variant_id: int | None = None
    # Etsy variation product_id -> Printify variant_id, for multi-variant routing.
    variant_map: dict[str, int] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))


def load_store(path: str | Path = DEFAULT_STORE) -> dict[str, ListingRecord]:
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return {k: ListingRecord.model_validate(v) for k, v in data.items()}


def save_store(records: dict[str, ListingRecord], path: str | Path = DEFAULT_STORE) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({k: v.model_dump() for k, v in records.items()}, indent=2))


def save_record(record: ListingRecord, path: str | Path = DEFAULT_STORE) -> None:
    records = load_store(path)
    records[record.etsy_listing_id] = record
    save_store(records, path)


def published_slugs(records: dict[str, ListingRecord]) -> set[str]:
    """Concept slugs already published — used to dedupe the planner."""
    return {r.slug for r in records.values() if r.slug}
