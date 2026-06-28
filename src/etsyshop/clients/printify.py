"""Printify REST API client.

Docs: https://developers.printify.com/
Auth: Personal Access Token (Bearer). Base URL: https://api.printify.com/v1/
"""

from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://api.printify.com/v1"


class PrintifyError(RuntimeError):
    pass


class PrintifyClient:
    def __init__(self, token: str, shop_id: str | None = None, timeout: float = 30.0):
        if not token:
            raise PrintifyError("PRINTIFY_API_TOKEN is not set.")
        self.shop_id = shop_id
        self._http = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "etsyshop/0.1",
            },
        )

    def __enter__(self) -> "PrintifyClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._http.request(method, path, **kwargs)
        if resp.status_code >= 400:
            raise PrintifyError(f"{method} {path} -> {resp.status_code}: {resp.text}")
        if resp.content:
            return resp.json()
        return None

    # --- Shops ---
    def list_shops(self) -> list[dict]:
        """All shops (sales channels) connected to this Printify account."""
        return self._request("GET", "/shops.json")

    # --- Catalog (read-only; useful for building product templates) ---
    def list_blueprints(self) -> list[dict]:
        """Product types, e.g. 'Unisex Heavy Cotton Tee'."""
        return self._request("GET", "/catalog/blueprints.json")

    def list_print_providers(self, blueprint_id: int) -> list[dict]:
        return self._request(
            "GET", f"/catalog/blueprints/{blueprint_id}/print_providers.json"
        )

    def list_variants(self, blueprint_id: int, print_provider_id: int) -> dict:
        return self._request(
            "GET",
            f"/catalog/blueprints/{blueprint_id}/"
            f"print_providers/{print_provider_id}/variants.json",
        )

    # --- Images ---
    def upload_image(self, file_name: str, *, url: str | None = None,
                     contents_b64: str | None = None) -> dict:
        """Upload an image to the Printify media library.

        Provide either a public `url` or base64 `contents_b64`. Returns the
        uploaded image record whose `id` is referenced in product print areas.
        """
        if bool(url) == bool(contents_b64):
            raise PrintifyError("Provide exactly one of url or contents_b64.")
        body = {"file_name": file_name}
        body["url" if url else "contents"] = url or contents_b64
        return self._request("POST", "/uploads/images.json", json=body)

    # --- Products ---
    def _shop(self, shop_id: str | None) -> str:
        sid = shop_id or self.shop_id
        if not sid:
            raise PrintifyError("No Printify shop_id set (PRINTIFY_SHOP_ID).")
        return sid

    def list_products(self, shop_id: str | None = None) -> dict:
        return self._request("GET", f"/shops/{self._shop(shop_id)}/products.json")

    def get_product(self, product_id: str, shop_id: str | None = None) -> dict:
        return self._request(
            "GET", f"/shops/{self._shop(shop_id)}/products/{product_id}.json"
        )

    def create_product(self, payload: dict, shop_id: str | None = None) -> dict:
        return self._request(
            "POST", f"/shops/{self._shop(shop_id)}/products.json", json=payload
        )

    def publish_product(self, product_id: str, shop_id: str | None = None,
                        publish: dict | None = None) -> Any:
        """Push a product to its connected sales channel (e.g. Etsy)."""
        body = publish or {
            "title": True, "description": True, "images": True,
            "variants": True, "tags": True, "keyFeatures": True, "shipping_template": True,
        }
        return self._request(
            "POST",
            f"/shops/{self._shop(shop_id)}/products/{product_id}/publish.json",
            json=body,
        )

    # --- Orders ---
    def list_orders(self, shop_id: str | None = None) -> dict:
        return self._request("GET", f"/shops/{self._shop(shop_id)}/orders.json")
