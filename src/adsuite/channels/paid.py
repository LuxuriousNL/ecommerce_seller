"""Paid campaign adapters: Meta Ads and Google Ads.

Each implements the PaidChannel seam. Without credentials the factory returns a
DryRun channel. Request shapes follow the Meta Marketing API and Google Ads API
and are mock-tested; the Google shape is simplified and should be validated
against the live API version before production use.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx

from adsuite.config import AdSettings, channel_available, settings
from adsuite.models import Campaign, ChannelResult, Creative, Metrics

GRAPH = "https://graph.facebook.com/v21.0"
GOOGLE_OAUTH = "https://oauth2.googleapis.com/token"
GOOGLE_ADS = "https://googleads.googleapis.com/v17"

DEFAULT_TARGETING = {"geo_locations": {"countries": ["US"]}}


def _check(resp) -> None:
    if resp.status_code >= 400:
        raise RuntimeError(f"{resp.status_code}: {resp.text}")


def normalize_meta_insights(data: dict) -> Metrics:
    """Meta /insights row -> normalized Metrics."""
    row = (data.get("data") or [{}])[0]
    clicks = int(row.get("inline_link_clicks", row.get("clicks", 0)) or 0)
    conversions = sum(
        int(float(a.get("value", 0)))
        for a in (row.get("actions") or [])
        if "purchase" in a.get("action_type", "") or "conversion" in a.get("action_type", "")
    )
    revenue = sum(
        float(a.get("value", 0))
        for a in (row.get("action_values") or [])
        if "purchase" in a.get("action_type", "")
    )
    return Metrics(impressions=int(row.get("impressions", 0) or 0), clicks=clicks,
                   spend=float(row.get("spend", 0) or 0),
                   conversions=conversions, revenue=revenue)


def normalize_google_insights(data) -> Metrics:
    """Google Ads searchStream batches -> normalized Metrics."""
    batches = data if isinstance(data, list) else [data]
    impr = clicks = cost = 0
    conv = val = 0.0
    for batch in batches:
        for r in batch.get("results", []):
            m = r.get("metrics", {})
            impr += int(m.get("impressions", 0) or 0)
            clicks += int(m.get("clicks", 0) or 0)
            cost += int(m.get("costMicros", 0) or 0)
            conv += float(m.get("conversions", 0) or 0)
            val += float(m.get("conversionsValue", 0) or 0)
    return Metrics(impressions=impr, clicks=clicks, spend=cost / 1_000_000,
                   conversions=int(conv), revenue=val)


@runtime_checkable
class PaidChannel(Protocol):
    name: str

    def create_campaign(self, campaign: Campaign, creative: Creative) -> ChannelResult: ...
    def pause(self, campaign_id: str) -> ChannelResult: ...
    def set_budget(self, object_id: str, daily_budget: float) -> ChannelResult: ...
    def insights(self, campaign_id: str) -> Metrics: ...


class DryRunPaidChannel:
    def __init__(self, name: str):
        self.name = name

    def create_campaign(self, campaign: Campaign, creative: Creative) -> ChannelResult:
        return ChannelResult(ok=True, dry_run=True,
                             ids={"campaign": f"dry-{self.name}-{campaign.name}"})

    def pause(self, campaign_id: str) -> ChannelResult:
        return ChannelResult(ok=True, dry_run=True, ids={"campaign": campaign_id})

    def set_budget(self, object_id: str, daily_budget: float) -> ChannelResult:
        return ChannelResult(ok=True, dry_run=True, ids={"object": object_id})

    def insights(self, campaign_id: str) -> Metrics:
        return Metrics()  # no data in dry-run


class MetaAdsChannel:
    name = "meta_paid"

    def __init__(self, access_token: str, ad_account_id: str, http=httpx):
        self.access_token = access_token
        self.ad_account = ad_account_id  # numeric id, no "act_" prefix
        self._http = http

    def _post(self, path: str, data: dict) -> dict:
        data = {**data, "access_token": self.access_token}
        r = self._http.post(f"{GRAPH}/{path}", data=data)
        _check(r)
        return r.json()

    def create_campaign(self, campaign: Campaign, creative: Creative) -> ChannelResult:
        try:
            acct = f"act_{self.ad_account}"
            c = self._post(f"{acct}/campaigns", {
                "name": campaign.name, "objective": "OUTCOME_TRAFFIC",
                "status": "PAUSED", "special_ad_categories": "[]",
            })
            adset = self._post(f"{acct}/adsets", {
                "name": f"{campaign.name} adset", "campaign_id": c["id"],
                "daily_budget": int(round(campaign.daily_budget * 100)),  # minor units
                "billing_event": "IMPRESSIONS", "optimization_goal": "LINK_CLICKS",
                "targeting": str(DEFAULT_TARGETING), "status": "PAUSED",
            })
            adcreative = self._post(f"{acct}/adcreatives", {
                "name": f"{creative.slug} creative",
                "object_story_spec": str({
                    "page_id": "", "link_data": {
                        "message": creative.paid_primary_text,
                        "link": creative.landing_url or campaign.landing_url,
                        "name": creative.paid_headline,
                    }}),
            })
            ad = self._post(f"{acct}/ads", {
                "name": f"{creative.slug} ad", "adset_id": adset["id"],
                "creative": str({"creative_id": adcreative["id"]}), "status": "PAUSED",
            })
            return ChannelResult(ok=True, ids={
                "campaign": c["id"], "adset": adset["id"],
                "adcreative": adcreative["id"], "ad": ad["id"]})
        except Exception as exc:  # noqa: BLE001
            return ChannelResult(ok=False, error=str(exc))

    def pause(self, campaign_id: str) -> ChannelResult:
        try:
            self._post(campaign_id, {"status": "PAUSED"})
            return ChannelResult(ok=True, ids={"campaign": campaign_id})
        except Exception as exc:  # noqa: BLE001
            return ChannelResult(ok=False, error=str(exc))

    def set_budget(self, object_id: str, daily_budget: float) -> ChannelResult:
        try:
            self._post(object_id, {"daily_budget": int(round(daily_budget * 100))})
            return ChannelResult(ok=True, ids={"object": object_id})
        except Exception as exc:  # noqa: BLE001
            return ChannelResult(ok=False, error=str(exc))

    def insights(self, campaign_id: str) -> Metrics:
        r = self._http.get(f"{GRAPH}/{campaign_id}/insights", params={
            "fields": "impressions,clicks,inline_link_clicks,spend,actions,action_values",
            "access_token": self.access_token,
        })
        _check(r)
        return normalize_meta_insights(r.json())


class GoogleAdsChannel:
    """Simplified Google Ads adapter (Search). Validate against live API version."""

    name = "google_ads"

    def __init__(self, developer_token: str, customer_id: str, *, refresh_token: str = "",
                 client_id: str = "", client_secret: str = "", access_token: str = "", http=httpx):
        self.developer_token = developer_token
        self.customer_id = customer_id.replace("-", "")
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = access_token
        self._http = http

    def _token(self) -> str:
        if self._access_token:
            return self._access_token
        r = self._http.post(GOOGLE_OAUTH, data={
            "grant_type": "refresh_token", "refresh_token": self.refresh_token,
            "client_id": self.client_id, "client_secret": self.client_secret,
        })
        _check(r)
        self._access_token = r.json()["access_token"]
        return self._access_token

    def _headers(self) -> dict:
        return {"developer-token": self.developer_token,
                "Authorization": f"Bearer {self._token()}"}

    def create_campaign(self, campaign: Campaign, creative: Creative) -> ChannelResult:
        try:
            body = {"mutateOperations": [
                {"campaignBudgetOperation": {"create": {
                    "name": f"{campaign.name} budget",
                    "amountMicros": int(round(campaign.daily_budget * 1_000_000)),
                    "deliveryMethod": "STANDARD",
                }}},
                {"campaignOperation": {"create": {
                    "name": campaign.name, "status": "PAUSED",
                    "advertisingChannelType": "SEARCH", "manualCpc": {},
                }}},
            ]}
            r = self._http.post(f"{GOOGLE_ADS}/customers/{self.customer_id}/googleAds:mutate",
                                json=body, headers=self._headers())
            _check(r)
            results = r.json().get("mutateOperationResponses", [])
            return ChannelResult(ok=True, ids={"results": results})
        except Exception as exc:  # noqa: BLE001
            return ChannelResult(ok=False, error=str(exc))

    def pause(self, campaign_id: str) -> ChannelResult:
        try:
            body = {"mutateOperations": [{"campaignOperation": {"update": {
                "resourceName": f"customers/{self.customer_id}/campaigns/{campaign_id}",
                "status": "PAUSED"}, "updateMask": "status"}}]}
            r = self._http.post(f"{GOOGLE_ADS}/customers/{self.customer_id}/googleAds:mutate",
                                json=body, headers=self._headers())
            _check(r)
            return ChannelResult(ok=True, ids={"campaign": campaign_id})
        except Exception as exc:  # noqa: BLE001
            return ChannelResult(ok=False, error=str(exc))

    def set_budget(self, object_id: str, daily_budget: float) -> ChannelResult:
        try:
            body = {"mutateOperations": [{"campaignBudgetOperation": {"update": {
                "resourceName": f"customers/{self.customer_id}/campaignBudgets/{object_id}",
                "amountMicros": int(round(daily_budget * 1_000_000))},
                "updateMask": "amount_micros"}}]}
            r = self._http.post(f"{GOOGLE_ADS}/customers/{self.customer_id}/googleAds:mutate",
                                json=body, headers=self._headers())
            _check(r)
            return ChannelResult(ok=True, ids={"object": object_id})
        except Exception as exc:  # noqa: BLE001
            return ChannelResult(ok=False, error=str(exc))

    def insights(self, campaign_id: str) -> Metrics:
        query = (
            "SELECT metrics.impressions, metrics.clicks, metrics.cost_micros, "
            "metrics.conversions, metrics.conversions_value FROM campaign "
            f"WHERE campaign.id = {campaign_id}"
        )
        r = self._http.post(
            f"{GOOGLE_ADS}/customers/{self.customer_id}/googleAds:searchStream",
            json={"query": query}, headers=self._headers())
        _check(r)
        return normalize_google_insights(r.json())


def make_paid_channel(name: str, cfg: AdSettings | None = None) -> PaidChannel:
    cfg = cfg or settings
    if not channel_available(name, cfg):
        return DryRunPaidChannel(name)
    if name == "meta_paid":
        return MetaAdsChannel(cfg.meta_access_token, cfg.meta_ad_account_id)
    if name == "google_ads":
        return GoogleAdsChannel(
            cfg.google_ads_developer_token, cfg.google_ads_customer_id,
            refresh_token=cfg.google_ads_refresh_token,
            client_id=cfg.google_ads_client_id, client_secret=cfg.google_ads_client_secret)
    return DryRunPaidChannel(name)


class BudgetError(RuntimeError):
    pass


def launch_paid(
    creative: Creative,
    *,
    channels: list[str],
    daily_budget: float,
    name: str,
    objective: str = "traffic",
    landing_url: str = "",
    max_daily_budget: float = 20.0,
    cfg: AdSettings | None = None,
) -> dict[str, ChannelResult]:
    """Launch a paid campaign per channel, guarding against overspend."""
    if daily_budget > max_daily_budget:
        raise BudgetError(
            f"daily_budget {daily_budget} exceeds max {max_daily_budget}; raise --max-daily-budget")
    out: dict[str, ChannelResult] = {}
    for ch_name in channels:
        campaign = Campaign(name=name, channel=ch_name, objective=objective,
                            daily_budget=daily_budget, landing_url=landing_url or creative.landing_url)
        out[ch_name] = make_paid_channel(ch_name, cfg).create_campaign(campaign, creative)
    return out
