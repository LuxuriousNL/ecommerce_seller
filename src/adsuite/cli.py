"""adctl — the adsuite command-line interface."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Advertisement suite: organic, paid, and A/B experiments.",
                  no_args_is_help=True)
console = Console()


@app.command("organic")
def organic(
    slug: str = typer.Option(..., help="Creative slug."),
    image_url: list[str] = typer.Option(None, help="Hosted image URL(s)."),
    caption: str = typer.Option("", help="Organic caption."),
    hashtag: list[str] = typer.Option(None, help="Repeatable hashtag (no '#')."),
    channel: list[str] = typer.Option(None, help="facebook | instagram | tiktok (repeatable)."),
) -> None:
    """Post a creative to organic channels (dry-run automatically without creds)."""
    from adsuite.channels.organic import post_creative
    from adsuite.models import Creative

    channels = channel or ["facebook", "instagram", "tiktok"]
    creative = Creative(slug=slug, image_urls=image_url or [], organic_caption=caption,
                        hashtags=[h.lstrip("#") for h in (hashtag or [])])
    results = post_creative(creative, channels)
    table = Table("channel", "status", "post id", "note")
    for name, r in results.items():
        status = "dry-run" if r.dry_run else ("ok" if r.ok else "FAIL")
        table.add_row(name, status, r.post_id or "-", r.error or r.url or "")
    console.print(table)


if __name__ == "__main__":
    app()
