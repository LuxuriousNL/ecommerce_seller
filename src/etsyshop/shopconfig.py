"""Resolve shop-level ids a physical Etsy listing needs before it can go active.

A physical listing won't activate without a shipping profile (and Etsy expects a
return policy). These pick the shop's first/default of each.
"""

from __future__ import annotations

from etsyshop.clients.etsy import EtsyClient


def resolve_shipping_profile_id(etsy: EtsyClient, shop_id: str | None = None) -> int | None:
    profiles = etsy.get_shipping_profiles(shop_id).get("results") or []
    return int(profiles[0]["shipping_profile_id"]) if profiles else None


def resolve_return_policy_id(etsy: EtsyClient, shop_id: str | None = None) -> int | None:
    policies = etsy.get_return_policies(shop_id).get("results") or []
    return int(policies[0]["return_policy_id"]) if policies else None
