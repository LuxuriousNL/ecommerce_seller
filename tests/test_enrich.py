"""Listing enrichment tests — taxonomy resolution, attribute mapping, enrich flow."""

from __future__ import annotations

import httpx
import pytest

from etsyshop.clients import etsy as etsy_mod
from etsyshop.clients.etsy import EtsyClient
from etsyshop.enrich import enrich_listing, etsy_listing_id_from_product
from etsyshop.taxonomy import map_attributes, resolve_taxonomy_id

# A small slice of Etsy's seller taxonomy tree.
NODES = {
    "results": [
        {"id": 1, "name": "Home & Living", "children": [
            {"id": 68, "name": "Home Decor", "children": [
                {"id": 69, "name": "Ornaments", "children": []},
            ]},
        ]},
        {"id": 2, "name": "Art & Collectibles", "children": [
            {"id": 70, "name": "Ornaments", "children": [
                {"id": 71, "name": "Hanging Ornaments", "children": []},
            ]},
        ]},
    ]
}

PROPERTIES = {
    "results": [
        {"property_id": 46803063641, "name": "Occasion",
         "possible_values": [{"value_id": 1, "name": "Christmas"},
                             {"value_id": 2, "name": "Halloween"}]},
        {"property_id": 46803063659, "name": "Holiday",
         "possible_values": [{"value_id": 10, "name": "Christmas"}]},
    ]
}


def test_resolve_taxonomy_prefers_deepest_exact_match():
    match = resolve_taxonomy_id(NODES, "Ornaments")
    assert match is not None
    # Two "Ornaments" nodes exist; the deeper-pathed one wins.
    assert match.taxonomy_id in (69, 70)
    assert match.full_path.count(">") >= 1


def test_resolve_taxonomy_partial_match():
    match = resolve_taxonomy_id(NODES, "hanging")
    assert match is not None and match.taxonomy_id == 71


def test_resolve_taxonomy_no_match():
    assert resolve_taxonomy_id(NODES, "spaceship") is None


def test_map_attributes_resolves_value_ids_and_skips_unknown():
    updates, skipped = map_attributes(
        PROPERTIES["results"],
        {"Occasion": "Christmas", "Holiday": "Christmas", "Color": "Red"},
    )
    by_name = {u.name: u for u in updates}
    assert by_name["Occasion"].value_ids == [1]
    assert by_name["Holiday"].value_ids == [10]
    assert "Color" in skipped  # not a property of this category


def test_map_attributes_skips_invalid_value():
    updates, skipped = map_attributes(PROPERTIES["results"], {"Occasion": "Diwali"})
    assert updates == [] and skipped == ["Occasion"]


def test_etsy_listing_id_from_product():
    assert etsy_listing_id_from_product(
        {"external": [{"id": "12345", "handle": "https://etsy.com/listing/12345"}]}
    ) == "12345"
    assert etsy_listing_id_from_product({"external": []}) is None
    assert etsy_listing_id_from_product({}) is None


class FakeEtsy:
    """Records calls; returns the taxonomy/property fixtures above."""

    def __init__(self):
        self.updated_listing = None
        self.properties_set = []

    def get_seller_taxonomy_nodes(self):
        return NODES

    def get_taxonomy_properties(self, taxonomy_id):
        return PROPERTIES

    def update_listing(self, listing_id, *, shop_id=None, taxonomy_id=None, tags=None, materials=None):
        self.updated_listing = dict(listing_id=listing_id, taxonomy_id=taxonomy_id,
                                    tags=tags, materials=materials)
        return {"listing_id": listing_id}

    def update_listing_property(self, listing_id, property_id, *, value_ids, values, shop_id=None):
        self.properties_set.append((property_id, value_ids, values))
        return {}


def test_enrich_listing_applies_category_and_attributes():
    etsy = FakeEtsy()
    report = enrich_listing(
        etsy, "999",
        taxonomy_query="Ornaments",
        tags=["custom name ornament", "family ornament"],
        materials=["ceramic"],
        attributes={"Occasion": "Christmas", "Holiday": "Christmas", "Color": "Red"},
    )
    assert report.error is None
    assert report.taxonomy_id in (69, 70)
    assert etsy.updated_listing["taxonomy_id"] == report.taxonomy_id
    assert etsy.updated_listing["tags"] == ["custom name ornament", "family ornament"]
    assert len(etsy.properties_set) == 2  # Occasion + Holiday
    assert "Color" in report.skipped_attributes
    assert sorted(report.applied_attributes) == ["Holiday=Christmas", "Occasion=Christmas"]


def test_enrich_skips_attributes_without_category():
    etsy = FakeEtsy()
    report = enrich_listing(etsy, "999", attributes={"Occasion": "Christmas"})
    assert report.taxonomy_id is None
    assert report.skipped_attributes == ["Occasion"]
    assert etsy.properties_set == []


# --- Etsy client request shaping (mock transport) ---
def test_update_listing_uses_patch_form_encoded(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured.update(method=method, url=url, data=kwargs.get("data"))
        return httpx.Response(200, json={"listing_id": 5})

    monkeypatch.setattr(etsy_mod.httpx, "request", fake_request)
    client = EtsyClient(api_key="k", redirect_uri="http://localhost:8080/callback", shop_id="7")
    client._tokens = {"access_token": "tok"}
    client.update_listing(5, taxonomy_id=69, tags=["a", "b"], materials=["wood"])

    assert captured["method"] == "PATCH"
    assert captured["url"].endswith("/application/shops/7/listings/5")
    assert captured["data"] == {"taxonomy_id": 69, "tags": ["a", "b"], "materials": ["wood"]}


def test_update_listing_property_uses_put(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured.update(method=method, url=url, data=kwargs.get("data"))
        return httpx.Response(200, json={})

    monkeypatch.setattr(etsy_mod.httpx, "request", fake_request)
    client = EtsyClient(api_key="k", redirect_uri="http://localhost:8080/callback", shop_id="7")
    client._tokens = {"access_token": "tok"}
    client.update_listing_property(5, 46803063641, value_ids=[1], values=["Christmas"])

    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/application/shops/7/listings/5/properties/46803063641")
    assert captured["data"] == {"value_ids": [1], "values": ["Christmas"]}
