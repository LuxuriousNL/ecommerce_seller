"""Persistent state for adsuite campaigns and experiments (git-ignored)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from pydantic import BaseModel, Field

DEFAULT_STORE = Path(".state/adsuite.json")


class ExperimentRecord(BaseModel):
    slug: str
    variant_a_product: str = ""
    variant_b_product: str = ""
    channels: list[str] = Field(default_factory=list)
    campaigns: dict[str, dict[str, str]] = Field(default_factory=dict)  # variant -> channel -> id
    status: str = "running"  # running | decided
    winner: str | None = None
    created_at: str = Field(default_factory=lambda: dt.datetime.now().isoformat(timespec="seconds"))


def load_experiments(path: str | Path = DEFAULT_STORE) -> dict[str, ExperimentRecord]:
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return {k: ExperimentRecord.model_validate(v) for k, v in data.get("experiments", {}).items()}


def save_experiment(record: ExperimentRecord, path: str | Path = DEFAULT_STORE) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    blob = json.loads(p.read_text()) if p.exists() else {}
    blob.setdefault("experiments", {})[record.slug] = record.model_dump()
    p.write_text(json.dumps(blob, indent=2))
