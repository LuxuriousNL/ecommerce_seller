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


@app.callback()
def _bootstrap() -> None:
    from etsyshop.logging_setup import setup_logging

    setup_logging()
printify_app = typer.Typer(help="Printify commands.")
etsy_app = typer.Typer(help="Etsy commands.")
catalog_app = typer.Typer(help="Browse Printify's catalog to build product templates.")
products_app = typer.Typer(help="Create and publish products.")
orders_app = typer.Typer(help="Order operations.")
grow_app = typer.Typer(help="Growth orchestrator (the closed loop).")
listing_app = typer.Typer(help="Enrich Etsy listings beyond what Printify can set.")
publish_app = typer.Typer(help="Architecture B: create and own the Etsy listing.")
app.add_typer(printify_app, name="printify")
app.add_typer(etsy_app, name="etsy")
app.add_typer(catalog_app, name="catalog")
app.add_typer(products_app, name="products")
app.add_typer(orders_app, name="orders")
app.add_typer(grow_app, name="grow")
app.add_typer(listing_app, name="listing")
app.add_typer(publish_app, name="publish")
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
    enrich: bool = typer.Option(False, help="After publish, set Etsy category + attributes."),
) -> None:
    """Upload designs, create Printify products, and optionally publish + enrich on Etsy."""
    tmpl = ProductTemplate.load(template)
    designs = DesignManifest.load(manifest).designs

    listing_fn = None
    if optimize:
        from etsyshop.optimize import optimize_listing  # lazy: avoids anthropic import otherwise

        def listing_fn(design):  # noqa: ANN001
            return optimize_listing(design, tmpl)

    etsy = _etsy() if enrich else None
    table = Table("design", "product_id", "published", "etsy listing", "error")
    with _printify() as p:
        for design in designs:
            listing = listing_fn(design) if listing_fn else None
            result = create_design_product(p, tmpl, design, listing=listing, publish=publish)
            etsy_note = "-"
            if enrich and result.published and result.product_id:
                etsy_note = _enrich_published(p, etsy, result.product_id, tmpl, listing)
            table.add_row(
                result.slug, result.product_id or "-",
                "yes" if result.published else "no", etsy_note, result.error or "",
            )
    console.print(table)


def _enrich_published(printify, etsy, product_id, tmpl, listing) -> str:
    """Best-effort: resolve the published Etsy listing id and apply category/attributes."""
    from etsyshop.enrich import enrich_listing, wait_for_etsy_listing_id

    listing_id = wait_for_etsy_listing_id(printify, product_id)
    if not listing_id:
        return "pending"
    report = enrich_listing(
        etsy, listing_id,
        taxonomy_query=tmpl.etsy_taxonomy,
        tags=(listing.tags if listing else tmpl.default_tags) or None,
        materials=(listing.materials if listing else tmpl.materials) or None,
        attributes=tmpl.etsy_attributes or None,
    )
    if report.error:
        return f"err: {report.error[:20]}"
    return f"{listing_id} (cat {report.taxonomy_id})" if report.taxonomy_id else listing_id


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
@grow_app.command("run")
def grow_run(
    concepts: int = typer.Option(2, help="Concepts per niche."),
    max_products: int = typer.Option(5, help="Max new products this cycle."),
    ad_budget: float = typer.Option(5.0, help="Daily ad budget per product."),
    max_ad_spend: float = typer.Option(20.0, help="Cumulative daily ad-spend cap."),
    kill_switch: bool = typer.Option(False, help="Halt the cycle immediately."),
) -> None:
    """Run one growth cycle (dry-run plan: real niches + decisions, simulated make/ads)."""
    from etsyshop.growth import Guardrails, build_plan_steps, run_cycle
    from etsyshop.store import load_store, published_slugs

    guard = Guardrails(max_new_products=max_products, max_daily_ad_spend=max_ad_spend,
                       kill_switch=kill_switch)
    report = run_cycle(build_plan_steps(), guardrails=guard,
                       seen_slugs=published_slugs(load_store()),
                       concepts_per_niche=concepts, ad_budget=ad_budget)
    console.print(f"[bold]Cycle[/bold] — would create {len(report.created)}, "
                  f"advertise {len(report.advertised)} (planned ${report.ad_spend_planned:.2f})")
    if report.halted:
        console.print(f"[yellow]halted:[/yellow] {report.halted}")
    if report.created:
        console.print(f"  create: {', '.join(report.created)}")
    if report.decisions:
        table = Table("product", "action", "reason")
        for d in report.decisions:
            table.add_row(d.key, d.action, d.reason)
        console.print(table)
    console.print("[dim]Dry-run plan. Wire live steps + creds to execute for real.[/dim]")


@app.command("profit")
def profit_cmd(scale_margin: float = typer.Option(0.25, help="Margin at/above which to scale.")) -> None:
    """Net-profit P&L per listing with scale/hold/kill decisions."""
    from etsyshop.profit import build_ledger, classify, rank, revenue_units_from_receipts
    from etsyshop.store import load_store

    receipts = _etsy().list_receipts().get("results") or []
    rev, units = revenue_units_from_receipts(receipts)
    ledger = build_ledger(revenue_by_key=rev, units_by_key=units)
    records = load_store()
    table = Table("listing", "slug", "units", "revenue", "fees", "net", "margin", "action")
    for pnl in rank(ledger):
        rec = records.get(pnl.key)
        d = classify(pnl, scale_margin=scale_margin)
        colour = {"scale": "green", "kill": "red"}.get(d.action, "yellow")
        table.add_row(pnl.key, rec.slug if rec else "-", str(pnl.units),
                      f"${pnl.revenue:.2f}", f"${pnl.platform_fees:.2f}", f"${pnl.net_profit:.2f}",
                      f"{pnl.margin*100:.0f}%", f"[{colour}]{d.action}[/{colour}]")
    console.print(table)
    if not receipts:
        console.print("[yellow]No orders yet — P&L needs sales data.[/yellow]")
    console.print("[dim]Note: COGS + ad spend default to 0 here; the orchestrator "
                  "supplies them for full net profit.[/dim]")


@app.command("winners")
def winners_cmd(top: int = typer.Option(10, help="How many top sellers to show.")) -> None:
    """Rank your listings by sales (units + revenue) to decide what to double down on."""
    from etsyshop.analytics import winners
    from etsyshop.store import load_store

    receipts = _etsy().list_receipts().get("results") or []
    records = load_store()
    table = Table("listing", "slug", "units", "revenue")
    for p in winners(receipts, top=top):
        rec = records.get(p.listing_id)
        table.add_row(p.listing_id, rec.slug if rec else "-", str(p.units), f"${p.revenue:.2f}")
    console.print(table)
    if not receipts:
        console.print("[yellow]No orders yet.[/yellow]")


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


# --- Architecture B: we create and own the Etsy listing ---
@publish_app.command("pod")
def publish_pod(
    template: str = typer.Option(..., help="Product template JSON (with etsy_taxonomy)."),
    manifest: str = typer.Option(..., help="Design manifest JSON."),
    shipping_profile_id: int = typer.Option(None, help="Etsy shipping profile id (physical)."),
    optimize: bool = typer.Option(True, help="Generate full SEO per design (Claude)."),
    activate: bool = typer.Option(False, help="Make listings live (default: draft)."),
) -> None:
    """POD via Architecture B: Printify renders -> we create & own the Etsy listing."""
    from etsyshop.mockups import select_mockups
    from etsyshop.publisher import draft_for_pod, publish_listing
    from etsyshop.store import ListingRecord, save_record

    tmpl = ProductTemplate.load(template)
    designs = DesignManifest.load(manifest).designs
    optimize_fn = None
    if optimize:
        from etsyshop.optimize import optimize_listing

        def optimize_fn(design):  # noqa: ANN001
            return optimize_listing(design, tmpl)

    etsy = _etsy()
    table = Table("design", "printify product", "etsy listing", "state", "imgs", "error")
    with _printify() as p:
        for design in designs:
            result = create_design_product(p, tmpl, design, listing=None, publish=False)
            if not result.product_id:
                table.add_row(design.slug, "-", "-", "-", "0", result.error or "")
                continue
            product = p.get_product(result.product_id)
            image_urls = [m.url for m in select_mockups(product)]
            listing = optimize_fn(design) if optimize_fn else None
            draft = draft_for_pod(tmpl, image_urls, listing=listing,
                                  shipping_profile_id=shipping_profile_id or None)
            # E5.1: reprice with the real Printify variant cost when available.
            from etsyshop.engine import product_cost_from_printify
            real_cost = product_cost_from_printify(product)
            if real_cost and tmpl.target_margin:
                from etsyshop.pricing import SCHEDULES, US, CostInputs, recommend_price
                fees = SCHEDULES.get(tmpl.fee_country, US)
                draft.price = recommend_price(
                    CostInputs(product_cost=real_cost), fees, target_margin=tmpl.target_margin
                ).list_price
            pub = publish_listing(etsy, draft, activate=activate, fetch=p.download)
            if pub.listing_id and not pub.error:
                save_record(ListingRecord(
                    etsy_listing_id=pub.listing_id, slug=design.slug,
                    printify_product_id=result.product_id,
                    default_variant_id=(tmpl.variant_ids[0] if tmpl.variant_ids else None),
                ))
            table.add_row(design.slug, result.product_id, pub.listing_id or "-",
                          pub.state, str(pub.images_uploaded), pub.error or "")
    console.print(table)
    console.print("[dim]Mapping saved to .state/listings.json for order fulfillment.[/dim]")


@app.command("fulfill")
def fulfill_cmd(
    receipt_id: str = typer.Option(..., help="Etsy receipt (order) id."),
    send: bool = typer.Option(False, help="Also send the Printify order to production."),
) -> None:
    """Manual bridge: turn an Etsy order into a Printify production order (Architecture B)."""
    from etsyshop.fulfill import fulfill_receipt
    from etsyshop.store import load_store

    etsy = _etsy()
    receipt = etsy.get_receipt(receipt_id)
    with _printify() as p:
        res = fulfill_receipt(p, load_store(), receipt, send_to_production=send)
    console.print(f"Receipt {res.receipt_id}: orders created {res.orders_created or '-'}")
    if res.skipped_listings:
        console.print(f"[yellow]skipped (no mapping):[/yellow] {', '.join(res.skipped_listings)}")
    for err in res.errors:
        console.print(f"[red]error[/red] {err}")


# --- Listing enrichment: set Etsy category + attributes Printify can't ---
@listing_app.command("taxonomy")
def listing_taxonomy(search: str = typer.Option(..., help="Category name to resolve.")) -> None:
    """Resolve an Etsy category name to its taxonomy_id."""
    from etsyshop.taxonomy import resolve_taxonomy_id

    match = resolve_taxonomy_id(_etsy().get_seller_taxonomy_nodes(), search)
    if match:
        console.print(f"[green]{match.taxonomy_id}[/green] — {match.full_path}")
    else:
        console.print(f"[yellow]No category matched '{search}'.[/yellow]")


@listing_app.command("enrich")
def listing_enrich(
    listing_id: str = typer.Option(..., help="Etsy listing id (from the published product)."),
    taxonomy: str = typer.Option("", help="Etsy category name, e.g. 'Ornaments'."),
    tag: list[str] = typer.Option(None, help="Repeatable: --tag a --tag b (max 13)."),
    material: list[str] = typer.Option(None, help="Repeatable material term."),
    attr: list[str] = typer.Option(None, help="Repeatable attribute 'Name=Value', e.g. Occasion=Christmas."),
) -> None:
    """Apply category, tags, materials, and attributes to a published Etsy listing."""
    from etsyshop.enrich import enrich_listing

    attributes = {}
    for item in attr or []:
        if "=" not in item:
            raise typer.BadParameter(f"--attr must be Name=Value, got '{item}'")
        k, v = item.split("=", 1)
        attributes[k.strip()] = v.strip()

    report = enrich_listing(
        _etsy(), listing_id,
        taxonomy_query=taxonomy or None,
        tags=(tag or None),
        materials=(material or None),
        attributes=attributes or None,
    )
    if report.error:
        console.print(f"[red]FAIL[/red] - {report.error}")
        raise typer.Exit(1)
    if report.taxonomy_id:
        console.print(f"[green]category[/green] {report.taxonomy_id} ({report.taxonomy_path})")
    if report.applied_attributes:
        console.print(f"[green]attributes[/green] {', '.join(report.applied_attributes)}")
    if report.skipped_attributes:
        console.print(f"[yellow]skipped[/yellow] {', '.join(report.skipped_attributes)} "
                      "(not valid for this category)")
    console.print("Done.")


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
    publish: bool = typer.Option(False, help="Publish DIGITAL niche items via Architecture B."),
    printify_only: bool = typer.Option(False, help="Only POD-fulfillable niches."),
) -> None:
    """Build a trend-driven campaign plan: niches -> concepts -> priced listings."""
    from etsyshop.engine import plan_campaign
    from etsyshop.ideate import ideate
    from etsyshop.store import load_store, published_slugs

    optimize = optimize or publish  # publishing always needs full SEO
    listing_fn = None
    if optimize:
        from etsyshop.models import ProductTemplate
        from etsyshop.optimize import optimize_listing

        def listing_fn(concept):  # noqa: ANN001
            tmpl = ProductTemplate(name=concept.product_type, blueprint_id=0, print_provider_id=0)
            return optimize_listing(concept.to_design(), tmpl)

    already = published_slugs(load_store())  # E1.3 dedupe
    plan = plan_campaign(
        ideate, count_per_niche=count, max_niches=max_niches,
        target_margin=margin, listing_fn=listing_fn,
        printify_only=printify_only, skip_slugs=already,
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

    if publish:
        _publish_digital_items(plan, already)


def _publish_digital_items(plan, already_published: set[str]) -> None:
    """E1.1: publish digital-niche plan items end-to-end via Architecture B."""
    from etsyshop.design import create_design
    from etsyshop.engine import PublishedItem, publish_plan
    from etsyshop.publisher import draft_for_digital, publish_listing
    from etsyshop.store import ListingRecord, save_record
    from etsyshop.trends import load_trends

    niches = {n.slug: n for n in load_trends()}
    etsy = _etsy()

    def publish_item(item) -> "PublishedItem":  # noqa: ANN001
        niche = niches.get(item.niche_slug)
        if not niche or niche.kind != "digital":
            return PublishedItem(item.concept.slug, item.niche_slug, status="skipped")
        art = create_design(item.concept.slug, item.concept.design,
                            product_type=item.concept.product_type, qc=True)
        if art.status not in ("ready", "manual") or art.path is None:
            return PublishedItem(item.concept.slug, item.niche_slug, status="error",
                                 error=f"design {art.status}")
        draft = draft_for_digital(
            item.listing, price=item.price.list_price,
            taxonomy_query=niche.etsy_taxonomy, attributes=niche.etsy_attributes,
            digital_files=[str(art.path)], image_paths=[str(art.path)],
        )
        pub = publish_listing(etsy, draft, activate=False)
        if pub.listing_id and not pub.error:
            save_record(ListingRecord(etsy_listing_id=pub.listing_id, slug=item.concept.slug,
                                      kind="download"))
        return PublishedItem(item.concept.slug, item.niche_slug,
                             listing_id=pub.listing_id, status="published" if pub.listing_id else "error",
                             error=pub.error)

    results = publish_plan(plan, publish_item, skip_slugs=already_published)
    console.print("\n[bold]Published (digital):[/bold]")
    for r in results:
        console.print(f"  {r.slug}: {r.status} {r.listing_id or ''} {r.error or ''}")


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


# --- Architecture B live smoke test ---
@app.command("smoke")
def smoke_cmd(
    taxonomy: str = typer.Option("Ornaments", help="Category to test."),
    keep: bool = typer.Option(False, help="Don't delete the draft afterward."),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Create ONE real draft listing, verify what stuck, then delete it (Architecture B)."""
    from etsyshop.smoketest import smoke_test_b

    if not yes:
        typer.confirm("This creates a real (draft) Etsy listing. Continue?", abort=True)
    report = smoke_test_b(_etsy(), taxonomy_query=taxonomy, cleanup=not keep)
    if report.error:
        console.print(f"[red]FAIL[/red] - {report.error}")
        raise typer.Exit(1)
    console.print(f"Draft listing {report.listing_id} "
                  f"({'deleted' if report.cleaned_up else 'kept'}):")
    for c in report.checks:
        mark = "[green]OK[/green]" if c.ok else "[red]MISMATCH[/red]"
        console.print(f"  {mark} {c.field}: sent={c.sent!r} got={c.got!r}")
    console.print("[green]All fields stuck.[/green]" if report.all_ok
                  else "[yellow]Some fields didn't stick — see above.[/yellow]")


# --- Image generation seam ---
@app.command("design")
def design_cmd(
    slug: str = typer.Option(..., help="Output filename stem."),
    product_type: str = typer.Option("Poster", help="Product type (vector if sticker/tee)."),
    subject: str = typer.Option("", help="What to depict."),
    style: str = typer.Option("", help="Style/medium."),
    palette: str = typer.Option("", help="Colour palette."),
    niche: str = typer.Option("", help="Or: derive a brief from this niche via Claude."),
    qc: bool = typer.Option(True, help="Run the Claude-vision QC gate."),
) -> None:
    """Generate artwork from a design brief (or write the brief in manual mode)."""
    from etsyshop.design import create_design
    from etsyshop.models import DesignBrief

    if niche:
        from etsyshop.ideate import ideate
        from etsyshop.trends import load_trends

        n = next((x for x in load_trends() if x.slug == niche), None)
        if n is None:
            raise typer.BadParameter(f"Unknown niche '{niche}'.")
        concept = ideate(n, 1)[0]
        brief, product_type = concept.design, concept.product_type
        slug = slug or concept.slug
    else:
        if not subject:
            raise typer.BadParameter("Provide --subject (and ideally --style/--palette) or --niche.")
        brief = DesignBrief(subject=subject, style=style or "clean modern illustration",
                            palette=palette or "balanced, tasteful")

    art = create_design(slug, brief, product_type=product_type, qc=qc)
    console.print(f"[bold]{art.slug}[/bold] — status: {art.status} (provider: {art.provider})")
    if art.path:
        console.print(f"  file: {art.path}")
    if art.error:
        console.print(f"  [red]error:[/red] {art.error}")
    if art.qc and not art.qc.passed:
        console.print(f"  [yellow]QC issues:[/yellow] {', '.join(art.qc.issues)}")


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
