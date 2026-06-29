"""V.3: pin real-shaped API responses through our parsers so shapes don't drift."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from adsuite.channels.paid import normalize_google_insights, normalize_meta_insights
from etsyshop.engine import product_cost_from_printify
from etsyshop.enrich import etsy_listing_id_from_product
from etsyshop.mockups import select_mockups
from etsyshop.taxonomy import resolve_taxonomy_id
from shopkit.client import ShopifyClient

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_etsy_taxonomy_fixture_resolves():
    match = resolve_taxonomy_id(_load("etsy_taxonomy.json"), "Ornaments")
    assert match is not None and match.taxonomy_id == 69


def test_printify_product_fixture_parses():
    product = _load("printify_product.json")
    assert product_cost_from_printify(product) == 9.5          # min enabled cost
    assert etsy_listing_id_from_product(product) == "998877"   # published listing id
    mockups = select_mockups(product)
    assert mockups[0].url == "https://cdn/a.png"               # default first


def test_meta_insights_fixture_normalizes():
    m = normalize_meta_insights(_load("meta_insights.json"))
    assert m.impressions == 1200 and m.clicks == 48 and m.spend == 15.0
    assert m.conversions == 4 and m.revenue == 100.0


def test_google_insights_fixture_normalizes():
    m = normalize_google_insights(_load("google_insights.json"))
    assert m.impressions == 900 and m.spend == 12.0 and m.conversions == 5


def test_shopify_product_create_fixture_parses():
    fixture = _load("shopify_product_create.json")

    class FakeHttp:
        def post(self, url, json=None, headers=None):
            return httpx.Response(200, json=fixture)

    client = ShopifyClient("x.myshopify.com", "tok", http=FakeHttp())
    product = client.create_product(title="Tee")
    assert product["id"] == "gid://shopify/Product/55" and product["handle"] == "tee"
