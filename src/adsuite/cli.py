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


@app.command("paid")
def paid(
    name: str = typer.Option(..., help="Campaign name."),
    landing_url: str = typer.Option(..., help="Etsy listing URL to drive traffic to."),
    headline: str = typer.Option("", help="Paid ad headline."),
    primary_text: str = typer.Option("", help="Paid ad primary text."),
    daily_budget: float = typer.Option(5.0, help="Daily budget per channel."),
    max_daily_budget: float = typer.Option(20.0, help="Safety cap per channel."),
    channel: list[str] = typer.Option(None, help="meta_paid | google_ads (repeatable)."),
) -> None:
    """Launch a paid campaign (dry-run automatically without creds; budget-guarded)."""
    from adsuite.channels.paid import BudgetError, launch_paid
    from adsuite.creative import ensure_disclosure
    from adsuite.models import Creative

    channels = channel or ["meta_paid", "google_ads"]
    creative = Creative(slug=name, landing_url=landing_url, paid_headline=headline,
                        paid_primary_text=ensure_disclosure(primary_text) if primary_text else "")
    from adsuite.policy import review_creative
    for issue in review_creative(creative):
        console.print(f"[yellow]policy:[/yellow] {issue}")
    try:
        results = launch_paid(creative, channels=channels, daily_budget=daily_budget,
                              name=name, landing_url=landing_url,
                              max_daily_budget=max_daily_budget)
    except BudgetError as exc:
        console.print(f"[red]Budget guard:[/red] {exc}")
        raise typer.Exit(1) from exc
    table = Table("channel", "status", "ids", "error")
    for ch_name, r in results.items():
        status = "dry-run" if r.dry_run else ("ok" if r.ok else "FAIL")
        table.add_row(ch_name, status, str(r.ids) if r.ok else "-", r.error or "")
    console.print(table)


@app.command("report")
def report() -> None:
    """Summarize stored experiments (status, products, winner, campaigns)."""
    from adsuite.report import build_report
    from adsuite.store import load_experiments

    rows = build_report(load_experiments())
    if not rows:
        console.print("[yellow]No experiments recorded yet.[/yellow]")
        return
    table = Table("experiment", "status", "products", "winner", "campaigns", "channels")
    for r in rows:
        table.add_row(r["slug"], r["status"], r["products"], r["winner"],
                      str(r["campaigns"]), r["channels"])
    console.print(table)


@app.command("experiment")
def experiment(
    slug: str = typer.Option(..., help="Experiment slug."),
    product_a: str = typer.Option(..., help="Variant A product slug."),
    url_a: str = typer.Option(..., help="Variant A landing URL."),
    product_b: str = typer.Option(..., help="Variant B product slug."),
    url_b: str = typer.Option(..., help="Variant B landing URL."),
    daily_budget: float = typer.Option(10.0, help="Total daily budget (split across variants)."),
    channel: list[str] = typer.Option(None, help="meta_paid | google_ads (repeatable)."),
) -> None:
    """Launch an A/B experiment across two products (dry-run automatically without creds)."""
    from adsuite.experiment import launch_experiment
    from adsuite.models import Creative, Experiment, ExperimentVariant

    channels = channel or ["meta_paid", "google_ads"]
    exp = Experiment(
        slug=slug, channels=channels, daily_budget=daily_budget,
        variant_a=ExperimentVariant(label="A", product_slug=product_a, creative_slug=f"{product_a}-c"),
        variant_b=ExperimentVariant(label="B", product_slug=product_b, creative_slug=f"{product_b}-c"),
    )
    creatives = {
        "A": Creative(slug=f"{product_a}-c", product_slug=product_a, landing_url=url_a),
        "B": Creative(slug=f"{product_b}-c", product_slug=product_b, landing_url=url_b),
    }
    launched = launch_experiment(exp, creatives)
    table = Table("variant", "channel", "campaign id")
    for label, by_channel in launched.campaigns.items():
        for ch_name, cid in by_channel.items():
            table.add_row(label, ch_name, cid)
    console.print(table)
    for err in launched.errors:
        console.print(f"[yellow]{err}[/yellow]")
    console.print("[dim]Collect insights over a few days, then decide() to pick a winner.[/dim]")


if __name__ == "__main__":
    app()
