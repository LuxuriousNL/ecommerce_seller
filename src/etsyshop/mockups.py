"""Relay Printify-rendered mockups to an Etsy listing (Architecture B).

Printify still renders the design-on-product mockups; we just select, order
(hero first), and re-upload them to the listing we own. Selection/ordering is
pure logic here; the byte download + upload are done by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MockupImage:
    url: str
    rank: int
    is_default: bool


def select_mockups(product: dict, *, limit: int = 8) -> list[MockupImage]:
    """Pick and order a Printify product's rendered mockups, default image first.

    Etsy's first image is the click-driving thumbnail, so the Printify default
    mockup is ranked 1, then the rest in their existing order, capped at `limit`.
    """
    images = product.get("images") or []
    ordered = sorted(images, key=lambda im: (not im.get("is_default", False),))
    out: list[MockupImage] = []
    for rank, im in enumerate(ordered[:limit], start=1):
        src = im.get("src") or im.get("url")
        if not src:
            continue
        out.append(MockupImage(url=src, rank=rank, is_default=bool(im.get("is_default"))))
    return out
