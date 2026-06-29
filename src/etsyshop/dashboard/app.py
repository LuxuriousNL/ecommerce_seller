"""FastAPI control plane for etsyshop.

Serves a single-page dashboard plus a small JSON API over the same logic the CLI
uses. Build it with `create_app()`; run it with `etsyshop dashboard`.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from etsyshop.clients.etsy import EtsyClient
from etsyshop.clients.printify import PrintifyClient
from etsyshop.config import settings
from etsyshop.models import Design, ProductTemplate


def _result(fn: Callable[[], Any]) -> dict:
    """Run fn, returning {ok, data} or {ok: False, error} — never raise to the client."""
    try:
        return {"ok": True, "data": fn()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _printify() -> PrintifyClient:
    settings.require("printify_api_token")
    return PrintifyClient(settings.printify_api_token, settings.printify_shop_id)


def _etsy() -> EtsyClient:
    settings.require("etsy_api_key")
    return EtsyClient(settings.etsy_api_key, settings.etsy_redirect_uri, settings.etsy_shop_id)


class OptimizeRequest(BaseModel):
    product_type: str = "T-Shirt"
    slug: str = "design"
    title_hint: str = ""
    theme: str = ""
    niche: str = ""
    keywords: list[str] = []


def create_app() -> FastAPI:
    app = FastAPI(title="etsyshop dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/api/health")
    def health() -> dict:
        def printify_status() -> dict:
            with _printify() as p:
                shops = p.list_shops()
            return {"shops": len(shops), "shop_id": settings.printify_shop_id}

        def etsy_status() -> dict:
            e = _etsy()
            if not e.is_authorized:
                return {"authorized": False}
            return {"authorized": True, "user_id": e.whoami().get("user_id")}

        return {"printify": _result(printify_status), "etsy": _result(etsy_status)}

    @app.get("/api/trends")
    def trends() -> dict:
        def fetch() -> list[dict]:
            from etsyshop.trends import trending_now

            return [
                {"status": s.status, "slug": s.niche.slug, "name": s.niche.name,
                 "kind": s.niche.kind, "price_low": s.niche.price_low,
                 "price_high": s.niche.price_high}
                for s in trending_now()
            ]

        return _result(fetch)

    @app.get("/api/products")
    def products() -> dict:
        def fetch() -> list[dict]:
            with _printify() as p:
                data = p.list_products().get("data") or []
            return [{"id": d.get("id"), "title": d.get("title")} for d in data]

        return _result(fetch)

    @app.get("/api/orders")
    def orders() -> dict:
        from etsyshop.orders import reconcile

        def fetch() -> dict:
            with _printify() as p:
                report = reconcile(_etsy(), p)
            return {
                "etsy_receipts": report.etsy_receipt_count,
                "printify_orders": report.printify_order_count,
                "matched": report.matched,
                "issues": [vars(i) for i in report.issues],
            }

        return _result(fetch)

    @app.post("/api/optimize")
    def optimize(req: OptimizeRequest) -> dict:
        from etsyshop.optimize import optimize_listing

        def run() -> dict:
            template = ProductTemplate(
                name=req.product_type, blueprint_id=0, print_provider_id=0
            )
            design = Design(
                slug=req.slug, title_hint=req.title_hint, theme=req.theme,
                niche=req.niche, keywords=req.keywords,
            )
            listing = optimize_listing(design, template)
            return listing.model_dump()

        return _result(run)

    return app


INDEX_HTML = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>etsyshop dashboard</title>
<style>
  :root { color-scheme: light dark; }
  body { font: 15px/1.5 system-ui, sans-serif; margin: 0; padding: 2rem; max-width: 880px; }
  h1 { margin-top: 0; }
  section { border: 1px solid #8884; border-radius: 10px; padding: 1rem 1.25rem; margin: 1rem 0; }
  h2 { margin: 0 0 .5rem; font-size: 1.05rem; }
  button { font: inherit; padding: .4rem .8rem; border-radius: 7px; border: 1px solid #8886;
           background: #2563eb; color: #fff; cursor: pointer; }
  button.ghost { background: transparent; color: inherit; }
  input, textarea { font: inherit; width: 100%; box-sizing: border-box; padding: .4rem .5rem;
                    margin: .2rem 0 .6rem; border-radius: 7px; border: 1px solid #8886; background: transparent; color: inherit; }
  pre { background: #8881; padding: .75rem; border-radius: 7px; overflow-x: auto; white-space: pre-wrap; }
  .ok { color: #16a34a; } .bad { color: #dc2626; } .muted { opacity: .7; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }
</style>
</head>
<body>
  <h1>etsyshop <span class="muted">dashboard</span></h1>

  <section>
    <h2>Connections</h2>
    <button onclick="health()">Check</button>
    <pre id="health" class="muted">Click “Check”.</pre>
  </section>

  <section>
    <h2>Trends now <button class="ghost" onclick="trends()">Load</button></h2>
    <pre id="trends" class="muted">In-season niches (peak &gt; build &gt; upcoming).</pre>
  </section>

  <section>
    <h2>Products <button class="ghost" onclick="products()">Refresh</button></h2>
    <pre id="products" class="muted">—</pre>
  </section>

  <section>
    <h2>Orders <button class="ghost" onclick="orders()">Reconcile</button></h2>
    <pre id="orders" class="muted">—</pre>
  </section>

  <section>
    <h2>AI listing optimizer</h2>
    <div class="row">
      <div><label>Product type</label><input id="product_type" value="T-Shirt"></div>
      <div><label>Slug</label><input id="slug" value="retro-sunset-surf"></div>
    </div>
    <label>Title hint</label><input id="title_hint" value="Retro sunset surf graphic">
    <label>Theme</label><input id="theme" value="70s retro surf, warm sunset palette">
    <label>Niche</label><input id="niche" value="surfers and beach lovers">
    <label>Keywords (comma-separated)</label><input id="keywords" value="retro surf, sunset, vintage beach">
    <button onclick="optimize()">Generate SEO</button>
    <pre id="optimize" class="muted">—</pre>
  </section>

<script>
const show = (id, data) => { document.getElementById(id).textContent =
  typeof data === "string" ? data : JSON.stringify(data, null, 2); };
const get = async (id, url) => { show(id, "Loading…"); try {
  show(id, await (await fetch(url)).json()); } catch (e) { show(id, "Error: " + e); } };

const health   = () => get("health", "/api/health");
const trends   = () => get("trends", "/api/trends");
const products = () => get("products", "/api/products");
const orders   = () => get("orders", "/api/orders");

async function optimize() {
  show("optimize", "Generating… (calls Claude, ~a few seconds)");
  const body = {
    product_type: product_type.value, slug: slug.value, title_hint: title_hint.value,
    theme: theme.value, niche: niche.value,
    keywords: keywords.value.split(",").map(s => s.trim()).filter(Boolean),
  };
  try {
    const r = await fetch("/api/optimize", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body) });
    show("optimize", await r.json());
  } catch (e) { show("optimize", "Error: " + e); }
}
</script>
</body>
</html>
"""
