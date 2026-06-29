"""Structured logging setup. Call setup_logging() once at startup."""

from __future__ import annotations

import logging
import os

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_configured = False


def setup_logging(level: str | int | None = None) -> None:
    """Configure root logging once. Level from arg or ETSYSHOP_LOG_LEVEL (default INFO)."""
    global _configured
    if _configured:
        return
    lvl = level or os.environ.get("ETSYSHOP_LOG_LEVEL", "INFO")
    logging.basicConfig(level=lvl, format=_FORMAT)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"etsyshop.{name}")
