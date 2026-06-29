"""E5.3 multi-variant inventory + SKU fulfillment, and E5.7 logging."""

from __future__ import annotations

import logging

import httpx

from etsyshop.clients import etsy as etsy_mod
from etsyshop.clients.etsy import EtsyClient
from etsyshop.fulfill import build_printify_order
from etsyshop.inventory import build_inventory
from etsyshop.logging_setup import get_logger, setup_logging
from etsyshop.store import ListingRecord


# --- E5.3 ---
def test_build_inventory_sets_sku_and_property():
    products = build_inventory(
        [
            {"variant_id": 11, "price": 24.99, "option": "Small"},
            {"variant_id": 12, "price": 24.99, "option": "Large"},
        ],
        property_id=100, property_name="Size",
    )
    assert products[0]["sku"] == "11"
    assert products[0]["offerings"][0]["price"] == 24.99
    assert products[0]["property_values"][0]["values"] == ["Small"]
    assert products[1]["sku"] == "12"


def test_update_listing_inventory_puts_json(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured.update(method=method, url=url, json=kwargs.get("json"))
        return httpx.Response(200, json={})

    monkeypatch.setattr(etsy_mod.httpx, "request", fake_request)
    c = EtsyClient(api_key="k", redirect_uri="http://localhost:8080/callback")
    c._tokens = {"access_token": "t"}
    c.update_listing_inventory(555, [{"sku": "11", "offerings": []}])
    assert captured["method"] == "PUT"
    assert captured["url"].endswith("/application/listings/555/inventory")
    assert captured["json"]["products"][0]["sku"] == "11"


def test_fulfill_routes_by_sku():
    record = ListingRecord(etsy_listing_id="555", printify_product_id="p", default_variant_id=10)
    receipt = {"receipt_id": 1, "name": "A B", "country_iso": "US",
               "transactions": [{"listing_id": 555, "sku": "11", "quantity": 1}]}
    payload = build_printify_order(record, receipt)
    # SKU wins over the default variant
    assert payload["line_items"][0]["variant_id"] == 11


def test_fulfill_falls_back_when_no_sku():
    record = ListingRecord(etsy_listing_id="555", printify_product_id="p", default_variant_id=10)
    receipt = {"receipt_id": 1, "name": "A B", "country_iso": "US",
               "transactions": [{"listing_id": 555, "quantity": 1}]}
    payload = build_printify_order(record, receipt)
    assert payload["line_items"][0]["variant_id"] == 10


# --- E5.7 ---
def test_setup_logging_is_idempotent():
    setup_logging("DEBUG")
    setup_logging("INFO")  # second call is a no-op, shouldn't raise
    assert get_logger("publisher").name == "etsyshop.publisher"


def test_logger_emits(caplog):
    setup_logging()
    log = get_logger("test")
    with caplog.at_level(logging.INFO, logger="etsyshop.test"):
        log.info("hello %s", "world")
    assert "hello world" in caplog.text
