"""B live-smoke-test harness.

The Architecture B Etsy write calls are tested offline but unverified against the
live API. This creates ONE real draft listing (never activated), reads it back,
reports field-by-field what actually stuck, then deletes it. Run it once with
real credentials as the manual confirmation step.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from etsyshop.clients.etsy import EtsyClient
from etsyshop.taxonomy import resolve_taxonomy_id


def _norm(v: object) -> object:
    if isinstance(v, (list, tuple)):
        return sorted(str(x).strip().lower() for x in v)
    if isinstance(v, str):
        return v.strip().lower()
    return v


@dataclass
class FieldCheck:
    field: str
    sent: object
    got: object

    @property
    def ok(self) -> bool:
        return _norm(self.sent) == _norm(self.got)


@dataclass
class SmokeReport:
    listing_id: str | None = None
    checks: list[FieldCheck] = field(default_factory=list)
    cleaned_up: bool = False
    error: str | None = None

    @property
    def all_ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)


def smoke_test_b(
    etsy: EtsyClient,
    *,
    taxonomy_query: str = "Ornaments",
    title: str = "etsyshop smoke test — safe to delete",
    description: str = "Automated smoke test draft listing. Safe to delete.",
    price: float = 9.99,
    tags: list[str] | None = None,
    shop_id: str | None = None,
    cleanup: bool = True,
) -> SmokeReport:
    """Create a draft, read it back, diff sent vs stored, then delete it."""
    tags = tags or ["smoke test", "delete me"]
    report = SmokeReport()
    try:
        match = resolve_taxonomy_id(etsy.get_seller_taxonomy_nodes(), taxonomy_query)
        if not match:
            report.error = f"could not resolve category '{taxonomy_query}'"
            return report

        created = etsy.create_draft_listing(
            title=title, description=description, price=price,
            taxonomy_id=match.taxonomy_id, tags=tags, shop_id=shop_id,
        )
        report.listing_id = str(created.get("listing_id"))

        got = etsy.get_listing(report.listing_id)
        listing = (got.get("results") or [got])[0] if isinstance(got, dict) else {}
        report.checks = [
            FieldCheck("title", title, listing.get("title")),
            FieldCheck("taxonomy_id", match.taxonomy_id, listing.get("taxonomy_id")),
            FieldCheck("tags", tags, listing.get("tags")),
        ]

        if cleanup and report.listing_id:
            etsy.delete_listing(report.listing_id)
            report.cleaned_up = True
    except Exception as exc:  # noqa: BLE001
        report.error = str(exc)
    return report
