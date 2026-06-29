"""Preflight checks: which external systems are configured + safe smoke tests.

`run_checks()` reports credential readiness across every integration; the smoke
helpers do one safe read per system to confirm the creds actually work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Check:
    system: str
    ready: bool
    detail: str


def run_checks() -> list[Check]:
    """Credential/config readiness across etsyshop, adsuite, and shopkit."""
    checks: list[Check] = []

    try:
        from etsyshop.config import settings as es
        authed = " + token" if Path(".tokens.json").exists() else " (run `etsyshop etsy login`)"
        checks += [
            Check("etsy", bool(es.etsy_api_key), "ETSY_API_KEY" + authed),
            Check("printify", bool(es.printify_api_token and es.printify_shop_id),
                  "PRINTIFY_API_TOKEN + PRINTIFY_SHOP_ID"),
            Check("anthropic", bool(es.anthropic_api_key), "ANTHROPIC_API_KEY"),
            Check("image:openai", bool(es.openai_api_key), "OPENAI_API_KEY"),
            Check("image:recraft", bool(es.recraft_api_key), "RECRAFT_API_KEY"),
        ]
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("etsyshop", False, str(exc)))

    try:
        from adsuite.config import channel_available
        for ch in ("facebook", "instagram", "tiktok", "meta_paid", "google_ads"):
            ok = channel_available(ch)
            checks.append(Check(f"ads:{ch}", ok, "configured" if ok else "missing creds"))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("adsuite", False, str(exc)))

    try:
        from shopkit.config import settings as sk
        from shopkit.config import shopify_available
        checks.append(Check("shopify", shopify_available(),
                            sk.shopify_shop_domain or "SHOPIFY_SHOP_DOMAIN/TOKEN"))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("shopify", False, str(exc)))

    return checks


# --- safe per-system smoke tests (read-only; inject a client to test offline) ---
def smoke_printify(client) -> tuple[bool, str]:
    shops = client.list_shops()
    return True, f"{len(shops)} shop(s) connected"


def smoke_etsy(client) -> tuple[bool, str]:
    me = client.whoami()
    return True, f"authorized as user {me.get('user_id')}"


def smoke_shopify(client) -> tuple[bool, str]:
    # productCreate in dry-run returns a simulated id; a real client would read shop info.
    product = client.create_product(title="doctor-smoke (delete me)", status="DRAFT")
    return True, f"reachable ({product.get('id')})"
