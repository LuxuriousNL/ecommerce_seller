"""E5.1 real Printify cost + E5.2 client retry/backoff (mocked, no real sleeps)."""

from __future__ import annotations

import httpx
import pytest

from etsyshop.clients import etsy as etsy_mod
from etsyshop.clients.etsy import EtsyClient
from etsyshop.clients.printify import BASE_URL, PrintifyClient, PrintifyError
from etsyshop.engine import product_cost_from_printify


# --- E5.1 ---
def test_product_cost_from_printify_takes_min_enabled_cost():
    product = {"variants": [
        {"id": 1, "cost": 1100, "is_enabled": True},   # $11.00
        {"id": 2, "cost": 950, "is_enabled": True},    # $9.50  <- min
        {"id": 3, "cost": 100, "is_enabled": False},   # disabled, ignored
    ]}
    assert product_cost_from_printify(product) == 9.5


def test_product_cost_none_when_absent():
    assert product_cost_from_printify({"variants": []}) is None
    assert product_cost_from_printify({}) is None


# --- E5.2 Printify ---
def _printify(handler) -> PrintifyClient:
    client = PrintifyClient(token="x", shop_id="7")
    client._http = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    client._sleep = lambda d: None  # no real backoff
    return client


def test_printify_retries_on_429_then_succeeds():
    state = {"n": 0}

    def handler(request):
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="rate limited")
        return httpx.Response(200, json=[{"id": 1}])

    client = _printify(handler)
    assert client.list_shops()[0]["id"] == 1
    assert state["n"] == 2  # retried once


def test_printify_gives_up_after_max_retries():
    state = {"n": 0}

    def handler(request):
        state["n"] += 1
        return httpx.Response(503, text="down")

    client = _printify(handler)  # default max_retries=2 -> 3 attempts
    with pytest.raises(PrintifyError):
        client.list_shops()
    assert state["n"] == 3


# --- E5.2 Etsy ---
def test_etsy_retries_on_429(monkeypatch):
    state = {"n": 0}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, text="rl")
        return httpx.Response(200, json={"user_id": 5})

    monkeypatch.setattr(etsy_mod.httpx, "request", fake_request)
    client = EtsyClient(api_key="k", redirect_uri="http://localhost:8080/callback")
    client._tokens = {"access_token": "t"}
    client._sleep = lambda d: None
    assert client.whoami()["user_id"] == 5
    assert state["n"] == 2
