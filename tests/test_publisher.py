"""Architecture B publisher tests — create/own the Etsy listing (mocked)."""

from __future__ import annotations

import httpx

from etsyshop.clients import etsy as etsy_mod
from etsyshop.clients.etsy import EtsyClient
from etsyshop.models import ListingDraft, OptimizedListing, ProductTemplate
from etsyshop.mockups import select_mockups
from etsyshop.publisher import draft_for_pod, publish_listing

NODES = {"results": [{"id": 1, "name": "Home & Living", "children": [
    {"id": 69, "name": "Ornaments", "children": []}]}]}
PROPERTIES = {"results": [{"property_id": 99, "name": "Occasion",
                           "possible_values": [{"value_id": 1, "name": "Christmas"}]}]}


def test_select_mockups_puts_default_first():
    product = {"images": [
        {"src": "https://cdn/a.png", "is_default": False},
        {"src": "https://cdn/b.png", "is_default": True},
        {"src": "https://cdn/c.png", "is_default": False},
    ]}
    mockups = select_mockups(product)
    assert mockups[0].url == "https://cdn/b.png" and mockups[0].rank == 1
    assert [m.rank for m in mockups] == [1, 2, 3]


def test_draft_for_pod_prices_and_carries_etsy_fields():
    tmpl = ProductTemplate(
        name="Ceramic Ornament", blueprint_id=1, print_provider_id=1, variant_ids=[10],
        product_cost=5.0, target_margin=0.45,
        etsy_taxonomy="Ornaments", etsy_attributes={"Occasion": "Christmas"},
        materials=["ceramic"],
    )
    listing = OptimizedListing(title="Custom Family Ornament", tags=["family ornament"],
                               description="d", materials=["ceramic"])
    draft = draft_for_pod(tmpl, ["https://cdn/a.png"], listing=listing)
    assert draft.price > 5.0 and draft.listing_type == "physical"
    assert draft.taxonomy_query == "Ornaments"
    assert draft.attributes == {"Occasion": "Christmas"}
    assert draft.image_urls == ["https://cdn/a.png"]
    assert draft.alt_text == "Custom Family Ornament"


class FakeEtsy:
    def __init__(self):
        self.created = None
        self.images, self.files, self.props = [], [], []
        self.activated = False

    def get_seller_taxonomy_nodes(self):
        return NODES

    def get_taxonomy_properties(self, taxonomy_id):
        return PROPERTIES

    def create_draft_listing(self, **kw):
        self.created = kw
        return {"listing_id": 555}

    def upload_listing_image(self, listing_id, image, *, rank, alt_text=None, shop_id=None):
        self.images.append((rank, image, alt_text))
        return {}

    def upload_listing_file(self, listing_id, file_bytes, name, *, rank, shop_id=None):
        self.files.append((name, file_bytes, rank))
        return {}

    def update_listing_property(self, listing_id, property_id, *, value_ids, values, shop_id=None):
        self.props.append((property_id, values))
        return {}

    def activate_listing(self, listing_id, shop_id=None):
        self.activated = True
        return {}


def test_publish_physical_full_flow():
    etsy = FakeEtsy()
    draft = ListingDraft(
        title="Custom Family Ornament", description="d", price=12.99,
        listing_type="physical", tags=["family ornament"], materials=["ceramic"],
        taxonomy_query="Ornaments", attributes={"Occasion": "Christmas", "Color": "Red"},
        image_urls=["https://cdn/a.png", "https://cdn/b.png"], alt_text="alt",
    )
    res = publish_listing(etsy, draft, activate=True, fetch=lambda url: b"imgbytes")

    assert res.error is None
    assert res.listing_id == "555"
    assert res.taxonomy_id == 69
    assert etsy.created["listing_type"] == "physical" and etsy.created["taxonomy_id"] == 69
    assert res.images_uploaded == 2
    assert etsy.images[0][0] == 1  # hero ranked first
    assert res.applied_attributes == ["Occasion=Christmas"]
    assert "Color" in res.skipped_attributes  # not valid for this category
    assert res.state == "active" and etsy.activated


def test_publish_digital_uploads_files(tmp_path):
    f = tmp_path / "planner.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    etsy = FakeEtsy()
    draft = ListingDraft(
        title="2027 Digital Planner", description="d", price=7.99,
        listing_type="download", taxonomy_query="Ornaments",  # any resolvable category
        digital_files=[str(f)],
    )
    res = publish_listing(etsy, draft, activate=False)
    assert res.files_uploaded == 1
    assert etsy.files[0][0] == "planner.pdf"
    assert etsy.created["listing_type"] == "download"
    assert res.state == "draft"  # not activated


def test_publish_fails_clearly_on_unresolvable_category():
    etsy = FakeEtsy()
    draft = ListingDraft(title="x", description="d", price=1.0, taxonomy_query="Spaceships")
    res = publish_listing(etsy, draft)
    assert res.listing_id is None
    assert "category" in res.error.lower()


# --- Etsy client B-method request shaping (mock transport) ---
def test_create_draft_listing_posts_form(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured.update(method=method, url=url, data=kwargs.get("data"))
        return httpx.Response(200, json={"listing_id": 1})

    monkeypatch.setattr(etsy_mod.httpx, "request", fake_request)
    c = EtsyClient(api_key="k", redirect_uri="http://localhost:8080/callback", shop_id="7")
    c._tokens = {"access_token": "t"}
    c.create_draft_listing(title="T", description="D", price=9.99, taxonomy_id=69,
                           listing_type="download", tags=["a"])
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/application/shops/7/listings")
    assert captured["data"]["type"] == "download" and captured["data"]["taxonomy_id"] == 69


def test_upload_listing_image_is_multipart(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured.update(method=method, url=url, files=kwargs.get("files"))
        return httpx.Response(200, json={})

    monkeypatch.setattr(etsy_mod.httpx, "request", fake_request)
    c = EtsyClient(api_key="k", redirect_uri="http://localhost:8080/callback", shop_id="7")
    c._tokens = {"access_token": "t"}
    c.upload_listing_image(555, b"bytes", rank=1, alt_text="hero")
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/application/shops/7/listings/555/images")
    assert "image" in captured["files"]
