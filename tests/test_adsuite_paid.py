"""Epic A3: paid channel seam + Meta Ads / Google Ads adapters + budget guard."""

from __future__ import annotations

import httpx
import pytest

from adsuite.channels import paid as paid_mod
from adsuite.channels.paid import (
    BudgetError,
    DryRunPaidChannel,
    GoogleAdsChannel,
    MetaAdsChannel,
    launch_paid,
    make_paid_channel,
)
from adsuite.config import AdSettings
from adsuite.models import Campaign, Creative

CREATIVE = Creative(slug="retro-tee", landing_url="https://etsy.com/listing/1",
                    paid_headline="Retro Surf Tee", paid_primary_text="Ad. Shop the tee.")
CAMPAIGN = Campaign(name="retro-test", channel="meta_paid", daily_budget=5.0,
                    landing_url="https://etsy.com/listing/1")


class FakeHttp:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, data=None, json=None, headers=None):
        self.calls.append({"url": url, "data": data, "json": json, "headers": headers})
        return self._responses.pop(0)


def test_dryrun_paid_without_creds():
    ch = make_paid_channel("meta_paid", AdSettings())
    assert isinstance(ch, DryRunPaidChannel)
    res = ch.create_campaign(CAMPAIGN, CREATIVE)
    assert res.dry_run and res.ok


def test_make_real_paid_channels():
    cfg = AdSettings(META_ACCESS_TOKEN="t", META_AD_ACCOUNT_ID="123",
                     GOOGLE_ADS_DEVELOPER_TOKEN="d", GOOGLE_ADS_CUSTOMER_ID="456",
                     GOOGLE_ADS_REFRESH_TOKEN="r")
    assert isinstance(make_paid_channel("meta_paid", cfg), MetaAdsChannel)
    assert isinstance(make_paid_channel("google_ads", cfg), GoogleAdsChannel)


def test_meta_creates_campaign_adset_creative_ad():
    http = FakeHttp([
        httpx.Response(200, json={"id": "camp_1"}),
        httpx.Response(200, json={"id": "adset_1"}),
        httpx.Response(200, json={"id": "cre_1"}),
        httpx.Response(200, json={"id": "ad_1"}),
    ])
    ch = MetaAdsChannel("tok", "123", http=http)
    res = ch.create_campaign(CAMPAIGN, CREATIVE)
    assert res.ok
    assert res.ids == {"campaign": "camp_1", "adset": "adset_1",
                       "adcreative": "cre_1", "ad": "ad_1"}
    # campaign created against act_<account>, objective + budget in minor units
    assert http.calls[0]["url"].endswith("/act_123/campaigns")
    assert http.calls[0]["data"]["objective"] == "OUTCOME_TRAFFIC"
    assert http.calls[1]["data"]["daily_budget"] == 500  # $5 -> 500 cents
    assert all(c["data"]["access_token"] == "tok" for c in http.calls)


def test_google_uses_access_token_and_mutate_shape():
    http = FakeHttp([httpx.Response(200, json={"mutateOperationResponses": [{"a": 1}]})])
    ch = GoogleAdsChannel("dev", "456-789", access_token="at", http=http)
    res = ch.create_campaign(CAMPAIGN, CREATIVE)
    assert res.ok and res.ids["results"] == [{"a": 1}]
    call = http.calls[0]
    assert call["url"].endswith("/customers/456789/googleAds:mutate")  # dashes stripped
    assert call["headers"]["developer-token"] == "dev"
    ops = call["json"]["mutateOperations"]
    assert any("campaignBudgetOperation" in o for o in ops)
    assert any("campaignOperation" in o for o in ops)
    assert ops[0]["campaignBudgetOperation"]["create"]["amountMicros"] == 5_000_000


def test_google_refreshes_token_when_needed():
    http = FakeHttp([
        httpx.Response(200, json={"access_token": "fresh"}),       # oauth refresh
        httpx.Response(200, json={"mutateOperationResponses": []}),  # mutate
    ])
    ch = GoogleAdsChannel("dev", "456", refresh_token="r", client_id="c",
                          client_secret="s", http=http)
    ch.create_campaign(CAMPAIGN, CREATIVE)
    assert http.calls[0]["url"].endswith("oauth2.googleapis.com/token")
    assert http.calls[1]["headers"]["Authorization"] == "Bearer fresh"


def test_launch_paid_budget_guard():
    with pytest.raises(BudgetError):
        launch_paid(CREATIVE, channels=["meta_paid"], daily_budget=50.0,
                    name="x", max_daily_budget=20.0, cfg=AdSettings())


def test_launch_paid_dryruns_without_creds(monkeypatch):
    monkeypatch.setattr(paid_mod, "settings", AdSettings())
    results = launch_paid(CREATIVE, channels=["meta_paid", "google_ads"],
                          daily_budget=5.0, name="x")
    assert set(results) == {"meta_paid", "google_ads"}
    assert all(r.dry_run for r in results.values())
