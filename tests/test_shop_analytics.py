"""E5.4 shipping/return auto-resolve + E5.5 winner tracking."""

from __future__ import annotations

from etsyshop.analytics import rank_listings, winners
from etsyshop.models import ListingDraft
from etsyshop.publisher import publish_listing

NODES = {"results": [{"id": 1, "name": "Home & Living", "children": [
    {"id": 69, "name": "Ornaments", "children": []}]}]}


# --- E5.4 ---
class FakeEtsyWithProfiles:
    def __init__(self):
        self.created = None

    def get_seller_taxonomy_nodes(self):
        return NODES

    def get_taxonomy_properties(self, taxonomy_id):
        return {"results": []}

    def get_shipping_profiles(self, shop_id=None):
        return {"results": [{"shipping_profile_id": 555}, {"shipping_profile_id": 777}]}

    def get_return_policies(self, shop_id=None):
        return {"results": [{"return_policy_id": 888}]}

    def create_draft_listing(self, **kw):
        self.created = kw
        return {"listing_id": 1}

    def activate_listing(self, listing_id, shop_id=None):
        return {}


def test_physical_publish_auto_resolves_shipping_and_return():
    etsy = FakeEtsyWithProfiles()
    draft = ListingDraft(title="Ornament", description="d", price=12.99,
                         listing_type="physical", taxonomy_query="Ornaments")
    res = publish_listing(etsy, draft, activate=False)
    assert res.error is None
    assert etsy.created["shipping_profile_id"] == 555   # first profile
    assert etsy.created["return_policy_id"] == 888


def test_explicit_shipping_profile_is_respected():
    etsy = FakeEtsyWithProfiles()
    draft = ListingDraft(title="Ornament", description="d", price=12.99,
                         listing_type="physical", taxonomy_query="Ornaments",
                         shipping_profile_id=999)
    publish_listing(etsy, draft, activate=False)
    assert etsy.created["shipping_profile_id"] == 999  # not overridden


# --- E5.5 ---
RECEIPTS = [
    {"receipt_id": 1, "transactions": [
        {"listing_id": 100, "quantity": 2, "price": {"amount": 1299, "divisor": 100}},
        {"listing_id": 200, "quantity": 1, "price": {"amount": 799, "divisor": 100}},
    ]},
    {"receipt_id": 2, "transactions": [
        {"listing_id": 100, "quantity": 1, "price": {"amount": 1299, "divisor": 100}},
    ]},
]


def test_rank_listings_aggregates_and_sorts():
    ranked = rank_listings(RECEIPTS)
    assert ranked[0].listing_id == "100"
    assert ranked[0].units == 3
    assert ranked[0].revenue == 38.97  # 3 * 12.99
    assert ranked[1].listing_id == "200" and ranked[1].units == 1


def test_winners_top_n():
    assert [p.listing_id for p in winners(RECEIPTS, top=1)] == ["100"]


def test_rank_empty():
    assert rank_listings([]) == []
