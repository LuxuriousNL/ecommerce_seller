"""adsuite configuration + channel availability detection."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Meta (Facebook + Instagram)
    meta_access_token: str = Field(default="", alias="META_ACCESS_TOKEN")
    meta_page_id: str = Field(default="", alias="META_PAGE_ID")
    meta_ig_user_id: str = Field(default="", alias="META_IG_USER_ID")
    meta_ad_account_id: str = Field(default="", alias="META_AD_ACCOUNT_ID")

    # TikTok
    tiktok_access_token: str = Field(default="", alias="TIKTOK_ACCESS_TOKEN")
    tiktok_advertiser_id: str = Field(default="", alias="TIKTOK_ADVERTISER_ID")

    # Google Ads
    google_ads_developer_token: str = Field(default="", alias="GOOGLE_ADS_DEVELOPER_TOKEN")
    google_ads_customer_id: str = Field(default="", alias="GOOGLE_ADS_CUSTOMER_ID")
    google_ads_refresh_token: str = Field(default="", alias="GOOGLE_ADS_REFRESH_TOKEN")
    google_ads_client_id: str = Field(default="", alias="GOOGLE_ADS_CLIENT_ID")
    google_ads_client_secret: str = Field(default="", alias="GOOGLE_ADS_CLIENT_SECRET")

    # Anthropic (creative copy)
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-opus-4-8", alias="ANTHROPIC_MODEL")

    def require(self, *names: str) -> None:
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            raise RuntimeError(f"Missing config: {', '.join(n.upper() for n in missing)}")


settings = AdSettings()

# What each channel needs to run live (else it degrades to dry-run).
_REQUIREMENTS = {
    "facebook": ("meta_access_token", "meta_page_id"),
    "instagram": ("meta_access_token", "meta_ig_user_id"),
    "tiktok": ("tiktok_access_token",),
    "meta_paid": ("meta_access_token", "meta_ad_account_id"),
    "google_ads": ("google_ads_developer_token", "google_ads_customer_id",
                   "google_ads_refresh_token"),
}


def channel_available(name: str, cfg: AdSettings | None = None) -> bool:
    cfg = cfg or settings
    reqs = _REQUIREMENTS.get(name)
    if not reqs:
        return False
    return all(getattr(cfg, r) for r in reqs)
