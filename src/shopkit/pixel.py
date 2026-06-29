"""Tracking pixel/tag config for a store (Meta Pixel + Google tag).

Conversion tracking + retargeting audiences — what makes the paid ads from
adsuite measurable and re-targetable on the owned store.
"""

from __future__ import annotations


def pixel_config(*, meta_pixel_id: str = "", google_tag_id: str = "") -> dict:
    """Settings blob for a Shopify web pixel (install via ShopifyClient.create_web_pixel)."""
    cfg: dict[str, str] = {}
    if meta_pixel_id:
        cfg["meta_pixel_id"] = meta_pixel_id
    if google_tag_id:
        cfg["google_tag_id"] = google_tag_id
    return cfg
