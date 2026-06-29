"""shopkit configuration + availability detection."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ShopSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    shopify_shop_domain: str = Field(default="", alias="SHOPIFY_SHOP_DOMAIN")  # xxx.myshopify.com
    shopify_admin_token: str = Field(default="", alias="SHOPIFY_ADMIN_TOKEN")
    shopify_api_version: str = Field(default="2025-01", alias="SHOPIFY_API_VERSION")


settings = ShopSettings()


def shopify_available(cfg: ShopSettings | None = None) -> bool:
    cfg = cfg or settings
    return bool(cfg.shopify_shop_domain and cfg.shopify_admin_token)
