"""Architecture B fulfillment-bridge + store tests (mocked Printify)."""

from __future__ import annotations

import httpx

from etsyshop.clients.printify import BASE_URL, PrintifyClient
from etsyshop.fulfill import build_printify_order, fulfill_receipt
from etsyshop.store import ListingRecord, load_store, save_record

RECEIPT = {
    "receipt_id": 9001,
    "name": "Jane Doe",
    "buyer_email": "jane@example.com",
    "first_line": "1 Main St",
    "second_line": "",
    "city": "Austin",
    "state": "TX",
    "zip": "78701",
    "country_iso": "US",
    "transactions": [
        {"listing_id": 555, "product_id": 8001, "quantity": 2},
        {"listing_id": 777, "product_id": 9999, "quantity": 1},  # unmapped
    ],
}


def test_build_printify_order_maps_lines_and_address():
    record = ListingRecord(
        etsy_listing_id="555", printify_product_id="prod_1",
        default_variant_id=10, variant_map={"8001": 11},
    )
    payload = build_printify_order(record, RECEIPT)
    assert payload["external_id"] == "etsy-9001"
    assert payload["line_items"] == [
        {"product_id": "prod_1", "variant_id": 11, "quantity": 2}  # variant_map wins
    ]
    addr = payload["address_to"]
    assert addr["first_name"] == "Jane" and addr["last_name"] == "Doe"
    assert addr["zip"] == "78701" and addr["country"] == "US"


def test_build_order_falls_back_to_default_variant():
    record = ListingRecord(etsy_listing_id="555", printify_product_id="p", default_variant_id=10)
    payload = build_printify_order(record, RECEIPT)
    assert payload["line_items"][0]["variant_id"] == 10  # no variant_map entry


class FakePrintify:
    def __init__(self):
        self.orders, self.produced = [], []

    def create_order(self, payload, shop_id=None):
        self.orders.append(payload)
        return {"id": "ord_1"}

    def send_to_production(self, order_id, shop_id=None):
        self.produced.append(order_id)
        return {}


def test_fulfill_receipt_creates_mapped_orders_skips_unmapped():
    records = {"555": ListingRecord(etsy_listing_id="555", printify_product_id="p", default_variant_id=10)}
    p = FakePrintify()
    res = fulfill_receipt(p, records, RECEIPT, send_to_production=True)
    assert res.orders_created == ["ord_1"]
    assert res.produced if False else p.produced == ["ord_1"]
    assert "777" in res.skipped_listings  # no mapping for that listing
    assert len(p.orders) == 1


def test_store_roundtrip(tmp_path):
    path = tmp_path / "listings.json"
    rec = ListingRecord(etsy_listing_id="555", slug="ornament", printify_product_id="p1",
                        default_variant_id=10)
    save_record(rec, path)
    loaded = load_store(path)
    assert loaded["555"].slug == "ornament"
    assert loaded["555"].printify_product_id == "p1"


def test_printify_create_order_and_production():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/orders.json"):
            return httpx.Response(200, json={"id": "ord_9"})
        return httpx.Response(200, json={})

    client = PrintifyClient(token="x", shop_id="7")
    client._http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    order = client.create_order({"line_items": []})
    client.send_to_production(order["id"])
    assert ("POST", "/v1/shops/7/orders.json") in calls
    assert ("POST", "/v1/shops/7/orders/ord_9/send_to_production.json") in calls
