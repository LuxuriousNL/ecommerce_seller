"""shopctl — the shopkit command-line interface."""

from __future__ import annotations

from pathlib import Path

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


@app.command("sync")
def sync(
    title: str = typer.Option(..., help="Product title."),
    description: str = typer.Option("", help="Product description."),
    tag: list[str] = typer.Option(None, help="Repeatable tag."),
    product_type: str = typer.Option("", help="Product type."),
    status: str = typer.Option("DRAFT", help="DRAFT | ACTIVE."),
) -> None:
    """Create a product on the store (dry-run automatically without creds)."""
    from types import SimpleNamespace

    from shopkit.client import make_client
    from shopkit.sync import sync_product

    listing = SimpleNamespace(title=title, description=description, tags=tag or [])
    res = sync_product(make_client(), listing, product_type=product_type, status=status)
    if res.error:
        console.print(f"[red]FAIL[/red] {res.error}")
        raise typer.Exit(1)
    tagsfx = " (dry-run)" if res.dry_run else ""
    console.print(f"product: {res.product_id} handle: {res.handle}{tagsfx}")


@app.command("feed")
def feed(
    from_file: str = typer.Option(..., "--from", help="JSON file: list of product dicts."),
    out: str = typer.Option("out/merchant-feed.tsv", help="Output feed path."),
    currency: str = typer.Option("USD", help="Currency code."),
) -> None:
    """Build a Google Merchant Center feed from a products JSON file."""
    import json

    from shopkit.feed import write_feed

    products = json.loads(Path(from_file).read_text())
    p = write_feed(products, out, currency=currency)
    console.print(f"wrote {len(products)} products -> {p}")


@app.command("gate")
def gate(min_scalers: int = typer.Option(1, help="Scaling products needed to provision.")) -> None:
    """Check whether current sales justify spinning up a dedicated store."""
    from etsyshop.profit import build_ledger, decisions, revenue_units_from_receipts

    from shopkit.gating import gate_store_creation

    try:
        from etsyshop.cli import _etsy
        receipts = _etsy().list_receipts().get("results") or []
    except Exception:  # noqa: BLE001
        receipts = []
    rev, units = revenue_units_from_receipts(receipts)
    ds = decisions(build_ledger(revenue_by_key=rev, units_by_key=units))
    ok, reason = gate_store_creation("(shop)", ds, min_scalers=min_scalers)
    console.print(f"{'[green]provision[/green]' if ok else '[yellow]hold[/yellow]'} — {reason}")


if __name__ == "__main__":
    app()
