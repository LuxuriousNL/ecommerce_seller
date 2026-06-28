"""Configuration loaded from environment / .env file."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Printify
    printify_api_token: str = Field(default="", alias="PRINTIFY_API_TOKEN")
    printify_shop_id: str = Field(default="", alias="PRINTIFY_SHOP_ID")

    # Etsy
    etsy_api_key: str = Field(default="", alias="ETSY_API_KEY")
    etsy_api_secret: str = Field(default="", alias="ETSY_API_SECRET")
    etsy_shop_id: str = Field(default="", alias="ETSY_SHOP_ID")
    etsy_redirect_uri: str = Field(
        default="http://localhost:8080/callback", alias="ETSY_REDIRECT_URI"
    )

    # Anthropic (Phase 2)
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-opus-4-8", alias="ANTHROPIC_MODEL")

    def require(self, *names: str) -> None:
        """Raise a clear error if any named setting is empty."""
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            keys = ", ".join(n.upper() for n in missing)
            raise RuntimeError(
                f"Missing required configuration: {keys}. "
                f"Set it in your .env file (see .env.example)."
            )


settings = Settings()
