"""Shopify Admin GraphQL client (+ dry-run fallback)."""

from __future__ import annotations

import httpx

from shopkit.config import ShopSettings, settings, shopify_available


class ShopifyError(RuntimeError):
    pass


def _check(resp) -> None:
    if resp.status_code >= 400:
        raise ShopifyError(f"{resp.status_code}: {resp.text}")


def _user_errors(payload: dict, key: str) -> dict:
    res = payload[key]
    if res.get("userErrors"):
        raise ShopifyError(str(res["userErrors"]))
    return res


class ShopifyClient:
    def __init__(self, shop_domain: str, access_token: str,
                 api_version: str = "2025-01", http=httpx):
        self.endpoint = f"https://{shop_domain}/admin/api/{api_version}/graphql.json"
        self.token = access_token
        self._http = http

    def _gql(self, query: str, variables: dict | None = None) -> dict:
        r = self._http.post(
            self.endpoint,
            json={"query": query, "variables": variables or {}},
            headers={"X-Shopify-Access-Token": self.token, "Content-Type": "application/json"})
        _check(r)
        body = r.json()
        if body.get("errors"):
            raise ShopifyError(str(body["errors"]))
        return body.get("data", {})

    def create_product(self, *, title: str, description_html: str = "", product_type: str = "",
                       tags: list[str] | None = None, status: str = "DRAFT") -> dict:
        q = ("mutation($input: ProductInput!){ productCreate(input:$input){ "
             "product{ id handle } userErrors{ field message } } }")
        data = self._gql(q, {"input": {
            "title": title, "descriptionHtml": description_html,
            "productType": product_type, "tags": tags or [], "status": status}})
        return _user_errors(data, "productCreate")["product"]

    def set_variant_price(self, product_id: str, variant_id: str, price: float) -> dict:
        q = ("mutation($pid: ID!, $variants: [ProductVariantsBulkInput!]!){ "
             "productVariantsBulkUpdate(productId:$pid, variants:$variants){ "
             "productVariants{ id price } userErrors{ field message } } }")
        data = self._gql(q, {"pid": product_id,
                             "variants": [{"id": variant_id, "price": f"{price:.2f}"}]})
        return _user_errors(data, "productVariantsBulkUpdate")

    def create_collection(self, *, title: str, description_html: str = "") -> dict:
        q = ("mutation($input: CollectionInput!){ collectionCreate(input:$input){ "
             "collection{ id handle } userErrors{ field message } } }")
        data = self._gql(q, {"input": {"title": title, "descriptionHtml": description_html}})
        return _user_errors(data, "collectionCreate")["collection"]

    def create_page(self, *, title: str, body_html: str = "") -> dict:
        q = ("mutation($page: PageCreateInput!){ pageCreate(page:$page){ "
             "page{ id } userErrors{ field message } } }")
        data = self._gql(q, {"page": {"title": title, "body": body_html}})
        return _user_errors(data, "pageCreate")["page"]


class DryRunShopifyClient:
    """No-network client that returns simulated ids (used without credentials)."""

    dry_run = True

    def __init__(self):
        self._n = 0

    def _id(self, kind: str) -> str:
        self._n += 1
        return f"gid://dry/{kind}/{self._n}"

    def create_product(self, *, title, description_html="", product_type="", tags=None, status="DRAFT"):
        return {"id": self._id("Product"), "handle": title.lower().replace(" ", "-"), "dry_run": True}

    def set_variant_price(self, product_id, variant_id, price):
        return {"dry_run": True}

    def create_collection(self, *, title, description_html=""):
        return {"id": self._id("Collection"), "handle": title.lower().replace(" ", "-"), "dry_run": True}

    def create_page(self, *, title, body_html=""):
        return {"id": self._id("Page"), "dry_run": True}


def make_client(cfg: ShopSettings | None = None):
    cfg = cfg or settings
    if not shopify_available(cfg):
        return DryRunShopifyClient()
    return ShopifyClient(cfg.shopify_shop_domain, cfg.shopify_admin_token, cfg.shopify_api_version)
