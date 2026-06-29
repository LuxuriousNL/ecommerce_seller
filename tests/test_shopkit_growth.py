"""Epic S (S.4-S.6): Merchant feed, pixel, store registry, profit gating."""

from __future__ import annotations

from shopkit.client import DryRunShopifyClient
from shopkit.feed import build_feed, write_feed
from shopkit.gating import gate_store_creation, qualifies_for_store
from shopkit.pixel import pixel_config
from shopkit.store import ShopRecord, load_shops, register_store, save_shop
from etsyshop.profit import ProfitDecision

PRODUCTS = [
    {"id": "p1", "title": "Retro Tee", "description": "Catch the wave.",
     "link": "https://shop/p1", "image_link": "https://cdn/p1.png", "price": 24.99, "brand": "X"},
    {"id": "p2", "title": "Sunset Mug", "description": "Morning vibes\twith tabs",
     "link": "https://shop/p2", "image_link": "https://cdn/p2.png", "price": 14.5, "brand": "X"},
]


# --- S.4 feed ---
def test_build_feed_tsv_shape():
    feed = build_feed(PRODUCTS, currency="USD")
    lines = feed.strip().split("\n")
    assert lines[0].split("\t")[0] == "id"
    assert "24.99 USD" in lines[1]
    assert lines[1].split("\t")[5] == "in stock"
    # tabs/newlines in description are sanitized so the TSV stays valid
    assert len(lines[2].split("\t")) == len(lines[0].split("\t"))


def test_write_feed(tmp_path):
    p = write_feed(PRODUCTS, tmp_path / "feed.tsv")
    assert p.exists() and "Retro Tee" in p.read_text()


# --- S.4 pixel ---
def test_pixel_config_and_install():
    cfg = pixel_config(meta_pixel_id="123", google_tag_id="G-9")
    assert cfg == {"meta_pixel_id": "123", "google_tag_id": "G-9"}
    assert pixel_config() == {}
    res = DryRunShopifyClient().create_web_pixel(cfg)
    assert res["dry_run"] and res["id"].startswith("gid://dry/WebPixel/")


# --- S.5 registry ---
def test_store_registry_roundtrip(tmp_path):
    path = tmp_path / "shops.json"
    save_shop(ShopRecord(niche_slug="halloween-svg", domain="hw.myshopify.com",
                         collection_id="gid://c/1", status="live"), path)
    shops = load_shops(path)
    assert shops["halloween-svg"].domain == "hw.myshopify.com"
    assert shops["halloween-svg"].status == "live"


def test_register_store_pending_vs_live(tmp_path):
    path = tmp_path / "shops.json"
    pending = register_store("dorm-decor", path=path)
    assert pending.status == "pending"
    live = register_store("dorm-decor", domain="d.myshopify.com", path=path)
    assert live.status == "live"
    assert load_shops(path)["dorm-decor"].domain == "d.myshopify.com"


# --- S.6 gating ---
def test_gate_requires_a_scaler():
    scalers = [ProfitDecision("a", "scale", "x"), ProfitDecision("b", "hold", "y")]
    assert qualifies_for_store(scalers)
    ok, reason = gate_store_creation("halloween-svg", scalers)
    assert ok and "provision" in reason


def test_gate_holds_without_scalers():
    holds = [ProfitDecision("a", "hold", "x"), ProfitDecision("b", "kill", "y")]
    assert not qualifies_for_store(holds)
    ok, reason = gate_store_creation("dorm-decor", holds)
    assert not ok and "hold" in reason


def test_gate_min_scalers_threshold():
    one = [ProfitDecision("a", "scale", "x")]
    assert not qualifies_for_store(one, min_scalers=2)
