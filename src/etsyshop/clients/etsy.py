"""Etsy Open API v3 client with OAuth2 (PKCE) helper.

Docs: https://developers.etsy.com/documentation/
Base URL: https://openapi.etsy.com/v3
Auth: every request needs `x-api-key: <keystring>` AND `Authorization: Bearer <token>`.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx

API_BASE = "https://openapi.etsy.com/v3"
CONNECT_URL = "https://www.etsy.com/oauth/connect"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
TOKEN_FILE = Path(".tokens.json")

# Scopes needed across all phases. Trim if your app requests fewer.
DEFAULT_SCOPES = ["shops_r", "shops_w", "listings_r", "listings_w", "transactions_r"]


class EtsyError(RuntimeError):
    pass


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


class _CallbackHandler(BaseHTTPRequestHandler):
    result: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.endswith("/callback"):
            self.send_response(404)
            self.end_headers()
            return
        _CallbackHandler.result = dict(urllib.parse.parse_qsl(parsed.query))
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>etsyshop: authorization received. You can close this tab.</h2>")

    def log_message(self, *args: object) -> None:  # silence
        pass


class EtsyClient:
    def __init__(self, api_key: str, redirect_uri: str, shop_id: str | None = None,
                 timeout: float = 30.0):
        if not api_key:
            raise EtsyError("ETSY_API_KEY is not set.")
        self.api_key = api_key
        self.redirect_uri = redirect_uri
        self.shop_id = shop_id
        self._timeout = timeout
        self._tokens = self._load_tokens()

    # --- Token persistence ---
    @staticmethod
    def _load_tokens() -> dict:
        if TOKEN_FILE.exists():
            return json.loads(TOKEN_FILE.read_text())
        return {}

    def _save_tokens(self, tokens: dict) -> None:
        self._tokens = tokens
        TOKEN_FILE.write_text(json.dumps(tokens, indent=2))

    @property
    def is_authorized(self) -> bool:
        return bool(self._tokens.get("access_token"))

    # --- OAuth flow ---
    def authorize(self, scopes: list[str] | None = None) -> dict:
        """Run the full PKCE flow via a local callback server. Returns tokens."""
        scopes = scopes or DEFAULT_SCOPES
        verifier, challenge = _pkce_pair()
        state = secrets.token_urlsafe(16)
        params = {
            "response_type": "code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        auth_url = f"{CONNECT_URL}?{urllib.parse.urlencode(params)}"

        parsed = urllib.parse.urlparse(self.redirect_uri)
        host, port = parsed.hostname or "localhost", parsed.port or 80
        server = HTTPServer((host, port), _CallbackHandler)
        _CallbackHandler.result = {}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        print(f"Opening browser to authorize. If it doesn't open, visit:\n{auth_url}\n")
        webbrowser.open(auth_url)

        while not _CallbackHandler.result:
            pass  # handler is on a daemon thread; loop until callback hits
        server.shutdown()
        result = _CallbackHandler.result

        if result.get("state") != state:
            raise EtsyError("OAuth state mismatch (possible CSRF).")
        if "code" not in result:
            raise EtsyError(f"Authorization failed: {result}")

        return self._exchange_code(result["code"], verifier)

    def _exchange_code(self, code: str, verifier: str) -> dict:
        data = {
            "grant_type": "authorization_code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "code": code,
            "code_verifier": verifier,
        }
        resp = httpx.post(TOKEN_URL, data=data, timeout=self._timeout)
        if resp.status_code >= 400:
            raise EtsyError(f"Token exchange failed {resp.status_code}: {resp.text}")
        tokens = resp.json()
        self._save_tokens(tokens)
        return tokens

    def _refresh(self) -> None:
        refresh_token = self._tokens.get("refresh_token")
        if not refresh_token:
            raise EtsyError("No refresh token; run `etsyshop etsy login` again.")
        data = {
            "grant_type": "refresh_token",
            "client_id": self.api_key,
            "refresh_token": refresh_token,
        }
        resp = httpx.post(TOKEN_URL, data=data, timeout=self._timeout)
        if resp.status_code >= 400:
            raise EtsyError(f"Token refresh failed {resp.status_code}: {resp.text}")
        self._save_tokens(resp.json())

    # --- Authenticated requests ---
    def _request(self, method: str, path: str, *, _retried: bool = False, **kwargs: Any) -> Any:
        if not self.is_authorized:
            raise EtsyError("Not authorized. Run `etsyshop etsy login` first.")
        headers = {
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self._tokens['access_token']}",
        }
        resp = httpx.request(
            method, f"{API_BASE}{path}", headers=headers, timeout=self._timeout, **kwargs
        )
        if resp.status_code == 401 and not _retried:
            self._refresh()
            return self._request(method, path, _retried=True, **kwargs)
        if resp.status_code >= 400:
            raise EtsyError(f"{method} {path} -> {resp.status_code}: {resp.text}")
        return resp.json() if resp.content else None

    # --- Convenience reads ---
    def whoami(self) -> dict:
        """The authorized user. `user_id` doubles as the default shop owner id."""
        return self._request("GET", "/application/users/me")

    def get_shop(self, shop_id: str | None = None) -> dict:
        sid = shop_id or self.shop_id
        if not sid:
            raise EtsyError("No ETSY_SHOP_ID set.")
        return self._request("GET", f"/application/shops/{sid}")

    def list_listings(self, shop_id: str | None = None, state: str = "active") -> dict:
        sid = shop_id or self.shop_id
        return self._request(
            "GET", f"/application/shops/{sid}/listings", params={"state": state}
        )

    def list_receipts(self, shop_id: str | None = None, **params: Any) -> dict:
        """Orders. Etsy models an order as a 'receipt'."""
        sid = shop_id or self.shop_id
        return self._request("GET", f"/application/shops/{sid}/receipts", params=params)

    # --- Listing enrichment (the fields Printify's Etsy sync does NOT set) ---
    def get_listing(self, listing_id: int | str) -> dict:
        return self._request("GET", f"/application/listings/{listing_id}")

    def get_seller_taxonomy_nodes(self) -> dict:
        """Etsy's category tree. Used to resolve a taxonomy_id (the Etsy category)."""
        return self._request("GET", "/application/seller-taxonomy/nodes")

    def get_taxonomy_properties(self, taxonomy_id: int) -> dict:
        """The attributes (and their valid values) a given category supports."""
        return self._request(
            "GET", f"/application/seller-taxonomy/nodes/{taxonomy_id}/properties"
        )

    def get_listing_properties(self, listing_id: int | str, shop_id: str | None = None) -> dict:
        sid = shop_id or self.shop_id
        return self._request(
            "GET", f"/application/shops/{sid}/listings/{listing_id}/properties"
        )

    def update_listing(
        self,
        listing_id: int | str,
        *,
        shop_id: str | None = None,
        taxonomy_id: int | None = None,
        tags: list[str] | None = None,
        materials: list[str] | None = None,
        **extra: Any,
    ) -> dict:
        """Set category / tags / materials on an existing listing (PATCH, form-encoded)."""
        sid = shop_id or self.shop_id
        data: dict[str, Any] = {}
        if taxonomy_id is not None:
            data["taxonomy_id"] = taxonomy_id
        if tags is not None:
            data["tags"] = tags  # httpx encodes a list as repeated form keys
        if materials is not None:
            data["materials"] = materials
        data.update(extra)
        return self._request(
            "PATCH", f"/application/shops/{sid}/listings/{listing_id}", data=data
        )

    def update_listing_property(
        self,
        listing_id: int | str,
        property_id: int,
        *,
        value_ids: list[int],
        values: list[str],
        scale_id: int | None = None,
        shop_id: str | None = None,
    ) -> dict:
        """Set an attribute (e.g. Occasion=Christmas) on a listing (PUT, form-encoded)."""
        sid = shop_id or self.shop_id
        data: dict[str, Any] = {"value_ids": value_ids, "values": values}
        if scale_id is not None:
            data["scale_id"] = scale_id
        return self._request(
            "PUT",
            f"/application/shops/{sid}/listings/{listing_id}/properties/{property_id}",
            data=data,
        )
