"""Epic 1 tests: digital draft, local-image upload, dedupe, publish_plan."""

from __future__ import annotations

import datetime as dt

from etsyshop.engine import CampaignItem, CampaignPlan, PublishedItem, publish_plan
from etsyshop.models import DesignBrief, ListingDraft, OptimizedListing, ProductConcept
from etsyshop.pricing import US, CostInputs, recommend_price
from etsyshop.publisher import draft_for_digital, publish_listing
from etsyshop.store import ListingRecord, published_slugs

NODES = {"results": [{"id": 1, "name": "Paper & Party Supplies", "children": [
    {"id": 50, "name": "Paper", "children": []}]}]}


def test_draft_for_digital_is_download_type():
    listing = OptimizedListing(title="2027 Digital Planner", tags=["digital planner"],
                               description="d", materials=[])
    draft = draft_for_digital(
        listing, price=7.99, taxonomy_query="Paper",
        digital_files=["designs/art/planner.pdf"], image_paths=["designs/art/planner.png"],
        attributes={"Occasion": "New Year"},
    )
    assert draft.listing_type == "download"
    assert draft.who_made == "i_did"
    assert draft.digital_files == ["designs/art/planner.pdf"]
    assert draft.image_paths == ["designs/art/planner.png"]
    assert draft.taxonomy_query == "Paper" and draft.attributes == {"Occasion": "New Year"}
    assert draft.title == "2027 Digital Planner"


class FakeEtsy:
    def __init__(self):
        self.images, self.files = [], []

    def get_seller_taxonomy_nodes(self):
        return NODES

    def get_taxonomy_properties(self, taxonomy_id):
        return {"results": []}

    def create_draft_listing(self, **kw):
        return {"listing_id": 42}

    def upload_listing_image(self, listing_id, image, *, rank, alt_text=None,
                             filename="mockup.png", shop_id=None):
        self.images.append((rank, filename, image))
        return {}

    def upload_listing_file(self, listing_id, file_bytes, name, *, rank, shop_id=None):
        self.files.append((name, rank))
        return {}

    def activate_listing(self, listing_id, shop_id=None):
        return {}


def test_publish_uploads_local_images_and_files(tmp_path):
    preview = tmp_path / "planner.png"
    preview.write_bytes(b"\x89PNG preview")
    download = tmp_path / "planner.pdf"
    download.write_bytes(b"%PDF data")
    etsy = FakeEtsy()
    draft = ListingDraft(
        title="2027 Planner", description="d", price=7.99, listing_type="download",
        taxonomy_query="Paper", image_paths=[str(preview)], digital_files=[str(download)],
    )
    res = publish_listing(etsy, draft, activate=False)
    assert res.error is None and res.listing_id == "42"
    assert res.images_uploaded == 1 and etsy.images[0][1] == "planner.png"
    assert res.files_uploaded == 1 and etsy.files[0][0] == "planner.pdf"


def test_published_slugs():
    records = {
        "1": ListingRecord(etsy_listing_id="1", slug="ghost-svg"),
        "2": ListingRecord(etsy_listing_id="2", slug="bat-svg"),
        "3": ListingRecord(etsy_listing_id="3", slug=""),  # no slug -> excluded
    }
    assert published_slugs(records) == {"ghost-svg", "bat-svg"}


def _item(slug: str) -> CampaignItem:
    concept = ProductConcept(
        slug=slug, product_type="SVG", niche_slug="halloween-svg",
        design=DesignBrief(subject="ghost", style="flat", palette="pink"),
    )
    price = recommend_price(CostInputs(product_cost=0.5), US, target_margin=0.85)
    return CampaignItem(niche_slug="halloween-svg", status="peak", concept=concept,
                        price=price, in_market_band=True)


def test_publish_plan_dedupes_and_collects():
    plan = CampaignPlan(generated_on=dt.date(2026, 8, 1),
                        items=[_item("ghost"), _item("bat"), _item("pumpkin")])

    def publish_item(item):
        if item.concept.slug == "pumpkin":
            raise RuntimeError("gen failed")
        return PublishedItem(item.concept.slug, item.niche_slug,
                             listing_id=f"L-{item.concept.slug}", status="published")

    results = publish_plan(plan, publish_item, skip_slugs={"bat"})
    by_slug = {r.slug: r for r in results}
    assert by_slug["bat"].status == "skipped"           # pre-published
    assert by_slug["ghost"].status == "published" and by_slug["ghost"].listing_id == "L-ghost"
    assert by_slug["pumpkin"].status == "error" and "gen failed" in by_slug["pumpkin"].error
