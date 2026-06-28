"""Design orchestrator: brief -> generate -> QC -> saved artifact.

Ties the pluggable image provider and the Claude-vision QC gate together and
writes a usable artifact (or, in manual mode, the brief for external generation).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import anthropic

from etsyshop.imagegen import ImageProvider, select_provider
from etsyshop.imageqc import QCResult, qc_image
from etsyshop.models import DesignBrief

ART_DIR = Path("designs/art")
BRIEF_DIR = Path("designs/briefs")


@dataclass
class DesignArtifact:
    slug: str
    status: str  # ready | qc_failed | manual | error
    path: Path | None = None
    provider: str = "manual"
    qc: QCResult | None = None
    error: str | None = None


def create_design(
    slug: str,
    brief: DesignBrief,
    *,
    product_type: str = "",
    qc: bool = True,
    provider: ImageProvider | None = None,
    qc_client: anthropic.Anthropic | None = None,
    art_dir: Path = ART_DIR,
    brief_dir: Path = BRIEF_DIR,
) -> DesignArtifact:
    """Generate artwork for one design. Falls back to writing the brief if no provider."""
    provider = provider or select_provider(product_type)

    # Manual mode: no image API — persist the brief for external generation.
    if provider is None:
        brief_dir.mkdir(parents=True, exist_ok=True)
        path = brief_dir / f"{slug}.txt"
        path.write_text(brief.to_prompt())
        return DesignArtifact(slug, "manual", path=path, provider="manual")

    try:
        image = provider.generate(brief, transparent=True)
    except Exception as exc:  # noqa: BLE001
        return DesignArtifact(slug, "error", provider=provider.name, error=str(exc))

    art_dir.mkdir(parents=True, exist_ok=True)
    path = art_dir / f"{slug}.{image.ext}"
    path.write_bytes(image.data)

    qc_result: QCResult | None = None
    status = "ready"
    if qc:
        try:
            qc_result = qc_image(image.data, brief, mime=image.mime, client=qc_client)
            if not qc_result.passed:
                status = "qc_failed"
        except Exception as exc:  # noqa: BLE001
            return DesignArtifact(slug, "error", path=path, provider=provider.name, error=str(exc))

    return DesignArtifact(slug, status, path=path, provider=provider.name, qc=qc_result)
