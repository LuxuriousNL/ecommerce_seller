"""Provision a niche store's brand, collection, and content."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BrandKit:
    palette: list[str]
    fonts: list[str]
    tagline: str


def brand_for_niche(niche) -> BrandKit:
    """Derive a simple brand palette/typeface from the niche."""
    slug = getattr(niche, "slug", "").lower()
    taxonomy = (getattr(niche, "etsy_taxonomy", "") or "").lower()
    palette = ["#F4F1EA", "#C46A4E", "#2B2B2B"]  # warm editorial default
    if "halloween" in slug:
        palette = ["#141414", "#FF7518", "#6A0DAD"]
    elif "ornament" in slug or "christmas" in taxonomy:
        palette = ["#0B3D2E", "#B00020", "#D4AF37"]
    elif "dorm" in slug or "coquette" in slug:
        palette = ["#FBE7EF", "#E59AB8", "#3A3A3A"]
    return BrandKit(palette=palette, fonts=["Fraunces", "Inter"],
                    tagline=getattr(niche, "name", slug))


@dataclass
class ProvisionResult:
    collection_id: str | None = None
    page_id: str | None = None
    brand: BrandKit | None = None
    dry_run: bool = False
    error: str | None = None


def provision_store(client, niche) -> ProvisionResult:
    """Create the niche collection + an About page and compute the brand kit."""
    try:
        brand = brand_for_niche(niche)
        positioning = ", ".join(getattr(niche, "micro_positioning", []) or [])
        coll = client.create_collection(
            title=getattr(niche, "name", niche.slug),
            description_html=f"<p>{getattr(niche, 'why', '')}</p>")
        page = client.create_page(
            title="About",
            body_html=f"<p>{brand.tagline} — {positioning}</p>")
        return ProvisionResult(
            collection_id=coll.get("id"), page_id=page.get("id"), brand=brand,
            dry_run=bool(coll.get("dry_run")))
    except Exception as exc:  # noqa: BLE001
        return ProvisionResult(error=str(exc))
