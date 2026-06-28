"""HTTP client tests using httpx mock transport — no real network."""

from __future__ import annotations

import httpx
import pytest

from etsyshop.clients import etsy as etsy_mod
from etsyshop.clients.etsy import EtsyClient
from etsyshop.clients.printify import BASE_URL, PrintifyClient, PrintifyError


def _printify_with_handler(handler) -> PrintifyClient:
    client = PrintifyClient(token="x")
    client._http = httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": "Bearer x", "User-Agent": "etsyshop/0.1"},
        transport=httpx.MockTransport(handler),
    )
    return client


def test_printify_list_shops_parses_json():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/shops.json"
        assert request.headers["Authorization"] == "Bearer x"
        return httpx.Response(200, json=[{"id": 1, "title": "My Etsy", "sales_channel": "etsy"}])

    client = _printify_with_handler(handler)
    shops = client.list_shops()
    assert shops[0]["id"] == 1


def test_printify_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, text="bad payload")

    client = _printify_with_handler(handler)
    with pytest.raises(PrintifyError) as exc:
        client.create_product({"title": "x"}, shop_id="9")
    assert "422" in str(exc.value)


def test_printify_upload_image_requires_one_source():
    client = PrintifyClient(token="x")
    with pytest.raises(PrintifyError):
        client.upload_image("a.png")  # neither url nor contents
    with pytest.raises(PrintifyError):
        client.upload_image("a.png", url="u", contents_b64="c")  # both


def test_printify_create_product_needs_shop_id():
    client = PrintifyClient(token="x")  # no shop_id set
    with pytest.raises(PrintifyError):
        client.create_product({"title": "x"})


def test_etsy_request_sends_auth_headers(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["headers"] = headers
        return httpx.Response(200, json={"user_id": 42})

    monkeypatch.setattr(etsy_mod.httpx, "request", fake_request)

    client = EtsyClient(api_key="key", redirect_uri="http://localhost:8080/callback")
    client._tokens = {"access_token": "tok"}  # pretend we're authorized
    me = client.whoami()

    assert me["user_id"] == 42
    assert captured["headers"]["x-api-key"] == "key"
    assert captured["headers"]["Authorization"] == "Bearer tok"
    assert captured["url"].endswith("/application/users/me")


def test_etsy_unauthorized_raises():
    client = EtsyClient(api_key="key", redirect_uri="http://localhost:8080/callback")
    client._tokens = {}
    assert not client.is_authorized
    with pytest.raises(etsy_mod.EtsyError):
        client.whoami()
