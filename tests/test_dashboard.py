"""Phase 4 dashboard API tests — FastAPI TestClient with mocked backends."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from etsyshop.dashboard import app as dash  # noqa: E402
from etsyshop.models import OptimizedListing  # noqa: E402


class FakePrintify:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def list_shops(self):
        return [{"id": 1, "title": "My Etsy", "sales_channel": "etsy"}]

    def list_products(self):
        return {"data": [{"id": "p1", "title": "Retro Tee"}]}

    def list_orders(self):
        return {"data": []}


class FakeEtsy:
    is_authorized = True

    def whoami(self):
        return {"user_id": 77}

    def list_receipts(self):
        return {"results": []}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(dash, "_printify", lambda: FakePrintify())
    monkeypatch.setattr(dash, "_etsy", lambda: FakeEtsy())
    return TestClient(dash.create_app())


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "etsyshop" in r.text


def test_health_reports_both_services(client):
    body = client.get("/api/health").json()
    assert body["printify"]["ok"] and body["printify"]["data"]["shops"] == 1
    assert body["etsy"]["ok"] and body["etsy"]["data"]["user_id"] == 77


def test_products_lists_titles(client):
    body = client.get("/api/products").json()
    assert body["ok"]
    assert body["data"][0]["title"] == "Retro Tee"


def test_orders_reconciles(client):
    body = client.get("/api/orders").json()
    assert body["ok"]
    assert body["data"]["printify_orders"] == 0
    assert body["data"]["issues"] == []


def test_optimize_endpoint(client, monkeypatch):
    import etsyshop.optimize as opt

    monkeypatch.setattr(
        opt, "optimize_listing",
        lambda design, template: OptimizedListing(
            title="Retro Sunset Surf Tee", tags=["retro surf"], description="d", materials=[]
        ),
    )
    r = client.post("/api/optimize", json={"product_type": "T-Shirt", "slug": "x", "theme": "surf"})
    body = r.json()
    assert body["ok"]
    assert body["data"]["title"] == "Retro Sunset Surf Tee"


def test_endpoint_errors_are_caught_not_raised(client, monkeypatch):
    def boom():
        raise RuntimeError("printify down")

    monkeypatch.setattr(dash, "_printify", boom)
    body = client.get("/api/products").json()
    assert body["ok"] is False
    assert "printify down" in body["error"]
