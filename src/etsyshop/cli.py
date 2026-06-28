"""etsyshop command-line interface."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from etsyshop.clients.etsy import EtsyClient
from etsyshop.clients.printify import PrintifyClient
from etsyshop.config import settings
from etsyshop.models import DesignManifest, ProductTemplate
from etsyshop.pipeline import create_design_product

app = typer.Typer(help="Automate Etsy POD via Printify.", no_args_is_help=True)
printify_app = typer.Typer(help="Printify commands.")
etsy_app = typer.Typer(help="Etsy commands.")
catalog_app = typer.Typer(help="Browse Printify's catalog to build product templates.")
products_app = typer.Typer(help="Create and publish products.")
orders_app = typer.Typer(help="Order operations.")
app.add_typer(printify_app, name="printify")
app.add_typer(etsy_app, name="etsy")
app.add_typer(catalog_app, name="catalog")
app.add_typer(products_app, name="products")
app.add_typer(orders_app, name="orders")
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


# --- Phase 1: catalog discovery (find blueprint/provider/variant ids for templates) ---
@catalog_app.command("blueprints")
def catalog_blueprints(search: str = typer.Option("", help="Filter by title substring.")) -> None:
    """List product blueprints; copy an id into a template's blueprint_id."""
    with _printify() as p:
        blueprints = p.list_blueprints()
    table = Table("id", "title", "brand")
    for b in blueprints:
        if search.lower() in b.get("title", "").lower():
            table.add_row(str(b.get("id")), b.get("title", ""), b.get("brand", ""))
    console.print(table)


@catalog_app.command("providers")
def catalog_providers(blueprint_id: int) -> None:
    """List print providers for a blueprint (use as print_provider_id)."""
    with _printify() as p:
        providers = p.list_print_providers(blueprint_id)
    table = Table("id", "title")
    for pr in providers:
        table.add_row(str(pr.get("id")), pr.get("title", ""))
    console.print(table)


@catalog_app.command("variants")
def catalog_variants(blueprint_id: int, print_provider_id: int) -> None:
    """List variant ids (sizes/colors) for a blueprint+provider."""
    with _printify() as p:
        data = p.list_variants(blueprint_id, print_provider_id)
    table = Table("variant_id", "title")
    for v in data.get("variants", []):
        table.add_row(str(v.get("id")), v.get("title", ""))
    console.print(table)


# --- Phase 1 + 2: bulk product creation, optionally AI-optimized ---
@products_app.command("create")
def products_create(
    template: str = typer.Option(..., help="Path to a product template JSON."),
    manifest: str = typer.Option(..., help="Path to a design manifest JSON."),
    optimize: bool = typer.Option(False, help="Generate AI SEO before creating (Phase 2)."),
    publish: bool = typer.Option(False, help="Publish to Etsy after creating."),
) -> None:
    """Upload designs, create Printify products, and optionally publish to Etsy."""
    tmpl = ProductTemplate.load(template)
    designs = DesignManifest.load(manifest).designs

    listing_fn = None
    if optimize:
        from etsyshop.optimize import optimize_listing  # lazy: avoids anthropic import otherwise

        def listing_fn(design):  # noqa: ANN001
            return optimize_listing(design, tmpl)

    table = Table("design", "product_id", "published", "error")
    with _printify() as p:
        for design in designs:
            listing = listing_fn(design) if listing_fn else None
            result = create_design_product(p, tmpl, design, listing=listing, publish=publish)
            table.add_row(
                result.slug,
                result.product_id or "-",
                "yes" if result.published else "no",
                result.error or "",
            )
    console.print(table)


# --- Phase 2: preview AI optimization for a single design ---
@app.command("optimize")
def optimize_cmd(
    template: str = typer.Option(..., help="Path to a product template JSON."),
    manifest: str = typer.Option(..., help="Path to a design manifest JSON."),
    slug: str = typer.Option(..., help="Slug of the design to optimize."),
) -> None:
    """Print AI-generated SEO for one design without creating anything."""
    from etsyshop.optimize import optimize_listing

    tmpl = ProductTemplate.load(template)
    design = next((d for d in DesignManifest.load(manifest).designs if d.slug == slug), None)
    if design is None:
        raise typer.BadParameter(f"No design with slug '{slug}' in manifest.")
    listing = optimize_listing(design, tmpl)
    console.print(f"[bold]Title[/bold] ({len(listing.title)} chars): {listing.title}")
    console.print(f"[bold]Tags[/bold] ({len(listing.tags)}): {', '.join(listing.tags)}")
    console.print(f"[bold]Materials[/bold]: {', '.join(listing.materials)}")
    console.print(f"[bold]Description[/bold]:\n{listing.description}")


# --- Phase 3: order reconciliation ---
@orders_app.command("status")
def orders_status() -> None:
    """Reconcile Etsy orders against Printify fulfillment; flag exceptions."""
    from etsyshop.orders import reconcile

    with _printify() as p:
        report = reconcile(_etsy(), p)
    console.print(
        f"Etsy receipts: {report.etsy_receipt_count} | "
        f"Printify orders: {report.printify_order_count} | matched: {report.matched}"
    )
    if report.ok:
        console.print("[green]No issues.[/green]")
        return
    table = Table("source", "order_id", "reason", "detail")
    for issue in report.issues:
        table.add_row(issue.source, issue.order_id, issue.reason, issue.detail)
    console.print(table)


# --- Trend engine: traverse niches -> concepts -> pricing ---
@app.command("trends")
def trends_cmd(
    printify_only: bool = typer.Option(True, help="Only POD-fulfillable niches."),
    kind: str = typer.Option("", help="Filter: pod | digital | physical."),
) -> None:
    """Show which niches are in season right now (peak > build > upcoming)."""
    from etsyshop.trends import trending_now

    scored = trending_now(printify_only=printify_only, kind=kind or None)
    table = Table("status", "niche", "kind", "price band", "margin", "why")
    for s in scored:
        n = s.niche
        table.add_row(
            s.status, n.name, n.kind, f"${n.price_low:g}-${n.price_high:g}",
            f"{int(n.margin_low * 100)}-{int(n.margin_high * 100)}%", n.why,
        )
    console.print(table)
    if not scored:
        console.print("[yellow]Nothing in season for this filter.[/yellow]")


@app.command("ideate")
def ideate_cmd(
    niche: str = typer.Option(..., help="Niche slug (see `etsyshop trends`)."),
    count: int = typer.Option(3, help="Number of concepts."),
) -> None:
    """Generate IP-safe product concepts for a niche (calls Claude)."""
    from etsyshop.ideate import ideate
    from etsyshop.trends import load_trends

    n = next((x for x in load_trends() if x.slug == niche), None)
    if n is None:
        raise typer.BadParameter(f"Unknown niche '{niche}'. Try `etsyshop trends`.")
    for c in ideate(n, count):
        console.print(f"[bold]{c.slug}[/bold] — {c.product_type} | {c.micro_positioning}")
        console.print(f"  title: {c.title_hint}")
        console.print(f"  design: {c.design.subject} / {c.design.style} / {c.design.palette}")
        console.print(f"  keywords: {', '.join(c.seed_keywords)}\n")


@app.command("plan")
def plan_cmd(
    count: int = typer.Option(2, help="Concepts per niche."),
    max_niches: int = typer.Option(3, help="How many niches to cover."),
    margin: float = typer.Option(0.40, help="Target net margin."),
    optimize: bool = typer.Option(False, help="Also generate full SEO per concept."),
) -> None:
    """Build a trend-driven campaign plan: niches -> concepts -> priced listings."""
    from etsyshop.engine import plan_campaign
    from etsyshop.ideate import ideate

    listing_fn = None
    if optimize:
        from etsyshop.models import ProductTemplate
        from etsyshop.optimize import optimize_listing

        def listing_fn(concept):  # noqa: ANN001
            tmpl = ProductTemplate(name=concept.product_type, blueprint_id=0, print_provider_id=0)
            return optimize_listing(concept.to_design(), tmpl)

    plan = plan_campaign(
        ideate, count_per_niche=count, max_niches=max_niches,
        target_margin=margin, listing_fn=listing_fn,
    )
    console.print(f"Plan for {plan.generated_on} — niches: {', '.join(plan.niches)}\n")
    table = Table("niche", "status", "concept", "price", "in band", "ad-safe floor")
    for i in plan.items:
        flag = "[green]yes[/green]" if i.in_market_band else "[yellow]no[/yellow]"
        table.add_row(
            i.niche_slug, i.status, i.concept.slug,
            f"${i.price.list_price:.2f}", flag, f"${i.price.ad_safe_floor:.2f}",
        )
    console.print(table)


@app.command("price")
def price_cmd(
    product_cost: float = typer.Option(..., help="POD base cost (your COGS)."),
    margin: float = typer.Option(0.40, help="Target net margin."),
    country: str = typer.Option("US", help="Fee schedule: US | UK | NL | FR."),
) -> None:
    """Fee-aware price recommendation for a single product cost."""
    from etsyshop.pricing import SCHEDULES, US, CostInputs, recommend_price

    fees = SCHEDULES.get(country.upper(), US)
    rec = recommend_price(CostInputs(product_cost=product_cost), fees, target_margin=margin)
    b = rec.breakdown
    console.print(f"List price: [bold]{b.currency} {rec.list_price:.2f}[/bold] "
                  f"(raw {rec.raw_price:.2f}, {rec.rounding})")
    console.print(f"Net profit: {b.net_profit:.2f} | net margin: {b.net_margin*100:.1f}%")
    console.print(f"Break-even: {rec.break_even:.2f} | ad-safe floor: {rec.ad_safe_floor:.2f}")
    console.print(f"Max safe discount: {rec.max_safe_discount*100:.0f}%")


# --- Phase 4: web dashboard ---
@app.command("dashboard")
def dashboard(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8000, help="Port."),
) -> None:
    """Launch the web dashboard (requires the 'dashboard' extra)."""
    try:
        import uvicorn
    except ImportError as exc:
        raise typer.BadParameter(
            "Dashboard deps missing. Install with: pip install -e '.[dashboard]'"
        ) from exc
    from etsyshop.dashboard.app import create_app

    console.print(f"Dashboard at http://{host}:{port}")
    uvicorn.run(create_app(), host=host, port=port)


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
