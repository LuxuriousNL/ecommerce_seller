"""etsyshop command-line interface."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from etsyshop.clients.etsy import EtsyClient
from etsyshop.clients.printify import PrintifyClient
from etsyshop.config import settings

app = typer.Typer(help="Automate Etsy POD via Printify.", no_args_is_help=True)
printify_app = typer.Typer(help="Printify commands.")
etsy_app = typer.Typer(help="Etsy commands.")
app.add_typer(printify_app, name="printify")
app.add_typer(etsy_app, name="etsy")
console = Console()


def _printify() -> PrintifyClient:
    settings.require("printify_api_token")
    return PrintifyClient(settings.printify_api_token, settings.printify_shop_id)


def _etsy() -> EtsyClient:
    settings.require("etsy_api_key")
    return EtsyClient(settings.etsy_api_key, settings.etsy_redirect_uri, settings.etsy_shop_id)


@printify_app.command("shops")
def printify_shops() -> None:
    """List Printify shops (use the id as PRINTIFY_SHOP_ID)."""
    with _printify() as p:
        shops = p.list_shops()
    table = Table("id", "title", "sales_channel")
    for s in shops:
        table.add_row(str(s.get("id")), s.get("title", ""), s.get("sales_channel", ""))
    console.print(table)


@etsy_app.command("login")
def etsy_login() -> None:
    """Run the Etsy OAuth (PKCE) flow and store tokens locally."""
    e = _etsy()
    e.authorize()
    console.print("[green]Authorized.[/green] Tokens saved to .tokens.json")


@etsy_app.command("whoami")
def etsy_whoami() -> None:
    """Show the authorized Etsy user."""
    me = _etsy().whoami()
    console.print(me)


@app.command("connect-test")
def connect_test() -> None:
    """Verify Printify + Etsy credentials are wired up correctly."""
    ok = True

    console.rule("Printify")
    try:
        with _printify() as p:
            shops = p.list_shops()
        console.print(f"[green]OK[/green] - {len(shops)} shop(s) connected.")
        for s in shops:
            marker = " <- PRINTIFY_SHOP_ID" if str(s.get("id")) == settings.printify_shop_id else ""
            console.print(f"  - {s.get('id')}: {s.get('title')} ({s.get('sales_channel')}){marker}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        console.print(f"[red]FAIL[/red] - {exc}")

    console.rule("Etsy")
    try:
        e = _etsy()
        if not e.is_authorized:
            console.print("[yellow]Not authorized.[/yellow] Run `etsyshop etsy login` first.")
        else:
            me = e.whoami()
            console.print(f"[green]OK[/green] - authorized as user_id={me.get('user_id')}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        console.print(f"[red]FAIL[/red] - {exc}")

    raise typer.Exit(code=0 if ok else 1)


if __name__ == "__main__":
    app()
