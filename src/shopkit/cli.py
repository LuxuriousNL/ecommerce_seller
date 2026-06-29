"""shopctl — the shopkit command-line interface."""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(help="Shopify niche-store factory (provision, sync, feed).",
                  no_args_is_help=True)
console = Console()


@app.command("status")
def status() -> None:
    """Show whether Shopify is connected (else dry-run)."""
    from shopkit.config import settings, shopify_available

    if shopify_available():
        console.print(f"[green]connected[/green] {settings.shopify_shop_domain}")
    else:
        console.print("[yellow]not configured[/yellow] — running in dry-run mode")


@app.command("provision")
def provision(niche: str = typer.Option(..., help="Niche slug from the trend catalog.")) -> None:
    """Provision a niche store (collection + about page + brand kit)."""
    from etsyshop.trends import load_trends
    from shopkit.client import make_client
    from shopkit.provision import provision_store

    n = next((x for x in load_trends() if x.slug == niche), None)
    if n is None:
        raise typer.BadParameter(f"unknown niche '{niche}'")
    res = provision_store(make_client(), n)
    if res.error:
        console.print(f"[red]FAIL[/red] {res.error}")
        raise typer.Exit(1)
    tag = " (dry-run)" if res.dry_run else ""
    console.print(f"collection: {res.collection_id} | page: {res.page_id}{tag}")
    console.print(f"brand palette: {res.brand.palette} fonts: {res.brand.fonts}")


if __name__ == "__main__":
    app()
