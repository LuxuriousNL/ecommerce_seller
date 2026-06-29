"""Epic S (S.1-S.3): Shopify client, provisioner, product sync."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from shopkit.client import (
    DryRunShopifyClient,
    ShopifyClient,
    ShopifyError,
    make_client,
)
from shopkit.config import ShopSettings, shopify_available
from shopkit.provision import brand_for_niche, provision_store
from shopkit.sync import build_product_input, sync_product


# --- config ---
def test_shopify_available():
    assert shopify_available(ShopSettings(SHOPIFY_SHOP_DOMAIN="x.myshopify.com", SHOPIFY_ADMIN_TOKEN="t"))
    assert not shopify_available(ShopSettings())


def test_make_client_dry_vs_real():
    assert isinstance(make_client(ShopSettings()), DryRunShopifyClient)
    real = make_client(ShopSettings(SHOPIFY_SHOP_DOMAIN="x.myshopify.com", SHOPIFY_ADMIN_TOKEN="t"))
    assert isinstance(real, ShopifyClient)


# --- client (mock GraphQL) ---
class FakeHttp:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self._responses.pop(0)


def test_create_product_graphql_shape():
    http = FakeHttp([httpx.Response(200, json={
        "data": {"productCreate": {"product": {"id": "gid://shopify/Product/1", "handle": "retro-tee"},
                                   "userErrors": []}}})])
    client = ShopifyClient("x.myshopify.com", "tok", http=http)
    product = client.create_product(title="Retro Tee", tags=["retro"], status="ACTIVE")
    assert product["id"].endswith("/Product/1") and product["handle"] == "retro-tee"
    call = http.calls[0]
    assert call["url"].endswith("/admin/api/2025-01/graphql.json")
    assert call["headers"]["X-Shopify-Access-Token"] == "tok"
    assert "productCreate" in call["json"]["query"]
    assert call["json"]["variables"]["input"]["title"] == "Retro Tee"


def test_create_product_raises_on_user_errors():
    http = FakeHttp([httpx.Response(200, json={
        "data": {"productCreate": {"product": None,
                                   "userErrors": [{"field": "title", "message": "blank"}]}}})])
    client = ShopifyClient("x.myshopify.com", "tok", http=http)
    with pytest.raises(ShopifyError):
        client.create_product(title="")


def test_dryrun_client_returns_simulated_ids():
    c = DryRunShopifyClient()
    p = c.create_product(title="Retro Tee")
    assert p["dry_run"] and p["id"].startswith("gid://dry/Product/")
    assert c.create_collection(title="Tees")["dry_run"]


# --- provision ---
def _niche(slug, name, **kw):
    return SimpleNamespace(slug=slug, name=name, why="why", micro_positioning=["a", "b"],
                           etsy_taxonomy=kw.get("taxonomy", ""))


def test_brand_for_niche_heuristics():
    assert "#FF7518" in brand_for_niche(_niche("halloween-svg", "Halloween")).palette
    xmas = brand_for_niche(_niche("personalised-ornaments", "Ornaments", taxonomy="Ornaments"))
    assert "#D4AF37" in xmas.palette


def test_provision_store_dryrun():
    res = provision_store(DryRunShopifyClient(), _niche("dorm-decor", "Dorm Decor"))
    assert res.error is None and res.dry_run
    assert res.collection_id and res.page_id
    assert res.brand.tagline == "Dorm Decor"


# --- sync ---
def test_build_product_input_maps_listing():
    listing = SimpleNamespace(title="Retro Tee", description="Catch the wave.", tags=["retro", "surf"])
    fields = build_product_input(listing, product_type="T-Shirt")
    assert fields["title"] == "Retro Tee"
    assert fields["description_html"] == "<p>Catch the wave.</p>"
    assert fields["tags"] == ["retro", "surf"] and fields["product_type"] == "T-Shirt"


def test_sync_product_dryrun():
    listing = SimpleNamespace(title="Retro Tee", description="d", tags=["retro"])
    res = sync_product(DryRunShopifyClient(), listing, product_type="T-Shirt")
    assert res.dry_run and res.product_id and res.handle == "retro-tee"
