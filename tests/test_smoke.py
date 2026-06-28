"""B smoke-test harness tests (mocked Etsy)."""

from __future__ import annotations

from etsyshop.smoketest import smoke_test_b

NODES = {"results": [{"id": 1, "name": "Home & Living", "children": [
    {"id": 69, "name": "Ornaments", "children": []}]}]}


class FakeEtsy:
    """Echoes created fields back on get_listing (simulates everything sticking)."""

    def __init__(self, *, override: dict | None = None):
        self.created = None
        self.deleted = None
        self.override = override or {}

    def get_seller_taxonomy_nodes(self):
        return NODES

    def create_draft_listing(self, **kw):
        self.created = kw
        return {"listing_id": 12345}

    def get_listing(self, listing_id):
        c = self.created
        listing = {"title": c["title"], "taxonomy_id": c["taxonomy_id"], "tags": c["tags"]}
        listing.update(self.override)
        return listing

    def delete_listing(self, listing_id):
        self.deleted = listing_id


def test_smoke_all_fields_stick_and_cleanup():
    etsy = FakeEtsy()
    report = smoke_test_b(etsy, taxonomy_query="Ornaments", cleanup=True)
    assert report.error is None
    assert report.listing_id == "12345"
    assert report.all_ok
    assert report.cleaned_up and etsy.deleted == "12345"
    assert etsy.created["taxonomy_id"] == 69


def test_smoke_detects_field_that_did_not_stick():
    # Etsy returns a different taxonomy than we sent -> mismatch surfaced.
    etsy = FakeEtsy(override={"taxonomy_id": 999})
    report = smoke_test_b(etsy, taxonomy_query="Ornaments")
    assert not report.all_ok
    bad = [c for c in report.checks if not c.ok]
    assert len(bad) == 1 and bad[0].field == "taxonomy_id"


def test_smoke_keep_does_not_delete():
    etsy = FakeEtsy()
    report = smoke_test_b(etsy, cleanup=False)
    assert not report.cleaned_up and etsy.deleted is None


def test_smoke_unresolvable_category_errors():
    report = smoke_test_b(FakeEtsy(), taxonomy_query="Spaceships")
    assert report.listing_id is None and "category" in report.error
