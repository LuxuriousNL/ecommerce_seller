"""Phase 1 pipeline tests — no network, a fake Printify client."""

from __future__ import annotations

import pytest

from etsyshop.models import Design, OptimizedListing, ProductTemplate
from etsyshop.pipeline import build_product_payload, create_design_product

TEMPLATE = ProductTemplate(
    name="Tee",
    blueprint_id=6,
    print_provider_id=99,
    variant_ids=[11873, 11874],
    price_cents=2499,
    default_tags=["graphic tee"],
    description_prefix="Soft tee.",
)
DESIGN = Design(slug="sunset", image_url="https://example.com/sunset.png", title_hint="Sunset")


def test_build_payload_uses_template_and_image():
    payload = build_product_payload(TEMPLATE, DESIGN, image_id="img_1")
    assert payload["blueprint_id"] == 6
    assert payload["print_provider_id"] == 99
    assert [v["id"] for v in payload["variants"]] == [11873, 11874]
    assert all(v["price"] == 2499 and v["is_enabled"] for v in payload["variants"])
    placeholder = payload["print_areas"][0]["placeholders"][0]
    assert placeholder["position"] == "front"
    assert placeholder["images"][0]["id"] == "img_1"
    assert payload["title"] == "Sunset"
    assert payload["tags"] == ["graphic tee"]


def test_build_payload_prefers_optimized_listing():
    listing = OptimizedListing(
        title="Retro Sunset Surf Tee",
        tags=[f"tag{i}" for i in range(13)],
        description="Catch the wave.",
        materials=["cotton"],
    )
    payload = build_product_payload(TEMPLATE, DESIGN, image_id="img_1", listing=listing)
    assert payload["title"] == "Retro Sunset Surf Tee"
    assert payload["description"] == "Catch the wave."
    assert len(payload["tags"]) == 13


class FakePrintify:
    def __init__(self, fail_create: bool = False):
        self.fail_create = fail_create
        self.uploaded = self.created = self.published = None

    def upload_image(self, file_name, *, url=None, contents_b64=None):
        self.uploaded = file_name
        return {"id": "img_1"}

    def create_product(self, payload):
        if self.fail_create:
            raise RuntimeError("boom")
        self.created = payload
        return {"id": 555}

    def publish_product(self, product_id):
        self.published = product_id


def test_create_design_product_happy_path_with_publish():
    client = FakePrintify()
    result = create_design_product(client, TEMPLATE, DESIGN, publish=True)
    assert result.product_id == "555"
    assert result.published is True
    assert result.error is None
    assert client.published == "555"
    assert client.created["blueprint_id"] == 6


def test_create_design_product_without_publish_does_not_publish():
    client = FakePrintify()
    result = create_design_product(client, TEMPLATE, DESIGN, publish=False)
    assert result.published is False
    assert client.published is None


def test_create_design_product_captures_errors():
    client = FakePrintify(fail_create=True)
    result = create_design_product(client, TEMPLATE, DESIGN, publish=True)
    assert result.product_id is None
    assert result.published is False
    assert "boom" in result.error
    assert client.published is None  # never reached publish


def test_design_without_image_is_an_error():
    client = FakePrintify()
    result = create_design_product(client, TEMPLATE, Design(slug="noimg"), publish=False)
    assert result.product_id is None
    assert "image_path" in result.error or "image_url" in result.error
