"""Epic A5: state store, etsyshop bridge, report, policy guardrails."""

from __future__ import annotations

from types import SimpleNamespace

from adsuite.bridge import creative_from_listing, winner_signal
from adsuite.policy import check_copy, review_creative
from adsuite.report import build_report
from adsuite.store import ExperimentRecord, load_experiments, save_experiment
from adsuite.models import Creative


# --- store ---
def test_experiment_store_roundtrip(tmp_path):
    path = tmp_path / "adsuite.json"
    rec = ExperimentRecord(slug="tee-vs-mug", variant_a_product="tee", variant_b_product="mug",
                           channels=["meta_paid"], status="decided", winner="A",
                           campaigns={"A": {"meta_paid": "c1"}, "B": {"meta_paid": "c2"}})
    save_experiment(rec, path)
    loaded = load_experiments(path)
    assert loaded["tee-vs-mug"].winner == "A"
    assert loaded["tee-vs-mug"].campaigns["A"]["meta_paid"] == "c1"


def test_load_experiments_missing_file(tmp_path):
    assert load_experiments(tmp_path / "nope.json") == {}


# --- bridge ---
def test_creative_from_listing_builds_landing_url():
    listing = SimpleNamespace(etsy_listing_id="12345", slug="retro-tee")
    cr = creative_from_listing(listing, image_urls=["https://cdn/x.png"])
    assert cr.landing_url == "https://www.etsy.com/listing/12345"
    assert cr.product_slug == "retro-tee"
    assert cr.image_urls == ["https://cdn/x.png"]


def test_winner_signal_only_when_decided():
    decided = ExperimentRecord(slug="e", variant_a_product="tee", variant_b_product="mug",
                               status="decided", winner="B")
    sig = winner_signal(decided)
    assert sig["winning_product"] == "mug" and sig["losing_product"] == "tee"
    assert sig["action"] == "scale"

    running = ExperimentRecord(slug="e2", status="running")
    assert winner_signal(running) is None


# --- report ---
def test_build_report():
    experiments = {
        "e1": ExperimentRecord(slug="e1", variant_a_product="tee", variant_b_product="mug",
                               channels=["meta_paid", "google_ads"], status="decided", winner="A",
                               campaigns={"A": {"meta_paid": "c", "google_ads": "d"}}),
    }
    rows = build_report(experiments)
    assert rows[0]["winner"] == "A"
    assert rows[0]["products"] == "tee vs mug"
    assert rows[0]["campaigns"] == 2


# --- policy ---
def test_check_copy_flags_prohibited_and_missing_disclosure():
    assert any("prohibited" in i for i in check_copy("Guaranteed to cure boredom"))
    assert "paid copy missing ad disclosure" in check_copy("Shop now", paid=True)
    assert check_copy("Ad. Shop the retro tee", paid=True) == []  # disclosed + clean


def test_review_creative_clean():
    clean = Creative(slug="x", organic_caption="Catch the wave.",
                     paid_headline="Retro Surf Tee", paid_primary_text="Ad. Shop the tee.")
    assert review_creative(clean) == []


def test_review_creative_flags_issues():
    bad = Creative(slug="x", organic_caption="Best in the world!",
                   paid_primary_text="Guaranteed results")  # no disclosure + claims
    issues = review_creative(bad)
    assert any("best in the world" in i for i in issues)
    assert any("disclosure" in i for i in issues)
