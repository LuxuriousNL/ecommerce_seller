# ecommerce_seller (`etsyshop`)

A modular automation platform for a **trend-driven print-on-demand business**:
detect trends → create products → optimize listings → price → publish to **Etsy
and Shopify** → advertise (organic + paid + A/B) → measure **true profit** → double
down on winners — optionally as one self-running loop.

> ⚠️ **Status:** all logic is built and **203 tests pass (ruff clean)**, but it runs
> **dry-run / mock-tested** until you add credentials. External API request shapes
> are unit- and fixture-tested; only some are verified against live APIs. Run
> `etsyshop doctor` to see what's configured. See [`docs/ONBOARDING.md`](docs/ONBOARDING.md).

## What it does

```
trends ─► ideate ─► design + Claude-vision QC ─► fee-aware price ─► listing SEO
                          │                                              │
        ┌──────────────────┘                                            └──────────────┐
        ▼                                                                               ▼
  ETSY (marketplace)                                              SHOPIFY niche stores (owned funnel)
  A: Printify-owned listing (auto-fulfill)                        catalog · brand · Merchant feed · pixel
  B: we own the listing (full SEO control)                                              │
        └────────────────────────► ADSUITE (organic · paid · A/B) ◄─────────────────────┘
                          (paid → Etsy/Shopify; Google Shopping/PMax; pixel)
                                            │
                          PROFITABILITY BRAIN (net P&L: rev − COGS − fees − ad spend)
                                            │
                          GROWTH ORCHESTRATOR → scale winners / kill losers / promote niche to its own store
```

## Packages (4 installable, one venv)

| Package | CLI | Does |
|---------|-----|------|
| `etsyshop` | `etsyshop` | Core: product creation, pricing, listing SEO, both Etsy publish paths, image generation + QC, orders/profit, the growth orchestrator |
| `trendscanner` | `trendscan` | Scan RSS / Google Trends / ecommerce JSON-LD → trend signals feeding the niche detector |
| `adsuite` | `adctl` | Organic posts (FB/IG/TikTok), paid campaigns (Meta/Google), A/B experiments |
| `shopkit` | `shopctl` | Shopify niche-store factory; profit-gated store creation; Merchant feed + pixel |

## Quickstart

```bash
python3.13 -m venv .venv && source .venv/bin/activate   # system python3 may be too old
pip install -e ".[dev,dashboard,images]"
pytest -q                 # 203 tests, no creds/network needed
cp .env.example .env      # add keys as you get them
etsyshop doctor           # shows what's configured

# Works offline today (dry-run):
etsyshop trends
etsyshop price --product-cost 5 --margin 0.45
etsyshop grow run         # dry-run plan of the whole loop
```

Add an **Anthropic** key to unlock the AI brain immediately:
```bash
etsyshop ideate --niche halloween-svg
etsyshop design --niche halloween-svg --slug ghost
```

## The closed loop

```bash
etsyshop grow run            # dry-run: real niches + profit decisions, simulated make/ads
etsyshop grow run --execute  # real loop (confirmation + guardrails): publish + advertise
```
Digital niches publish fully automatically; POD needs a product template with real
Printify catalog ids. Guardrails: max new products/cycle, ad-spend cap, kill switch,
halt-on-QC-failure.

## Documentation
- [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md) — full architecture, every module, decisions, use cases.
- [`docs/ONBOARDING.md`](docs/ONBOARDING.md) — credentials, approvals, first-run runbook.
- [`CLAUDE.md`](CLAUDE.md) — operating guide & conventions for contributors/agents.
- Backlogs: [`docs/BACKLOG.md`](docs/BACKLOG.md), [`docs/ADSUITE_BACKLOG.md`](docs/ADSUITE_BACKLOG.md), [`docs/GROWTH_BACKLOG.md`](docs/GROWTH_BACKLOG.md).

## Credentials at a glance
Instant: **Anthropic**, **OpenAI/Recraft**, **Printify**. Approval required: **Etsy**
(app review), **Meta**/**TikTok** (app review/audit), **Google Ads** (developer token),
**Shopify** (store + token). Each stage stays in dry-run until its credential is present.

## Development
```bash
pytest -q              # full suite (mock-tested; no billable calls)
ruff check src tests   # lint (CI runs both on push)
```
Conventions in [`CLAUDE.md`](CLAUDE.md). Built with Claude Opus 4.8.
