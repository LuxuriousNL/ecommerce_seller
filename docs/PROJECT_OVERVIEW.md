# etsyshop — Project Overview

A modular automation platform for running a trend-driven, print-on-demand (POD)
Etsy business end to end: **detect trends → create products → optimize listings →
price → publish (Etsy + Shopify) → advertise → measure true profit → double down
on winners**, optionally as one self-running loop.

- **4 installable packages**, **62 modules**, **203 tests** (all passing, ruff clean)
- **4 CLIs**: `etsyshop`, `trendscan`, `adctl`, `shopctl`
- Everything **mock-tested** and **dry-run without credentials**; live calls activate
  per-system as you add keys (`etsyshop doctor` shows readiness).
- Built across 29 commits (see [Build timeline](#build-timeline)).

> **Status caveat (read this):** external API request *shapes* are unit-tested but
> only some are verified against live APIs (no production credentials yet). Etsy
> writes, image generation, ad platforms, and Shopify are validated by composition
> tests + the `smoke`/`doctor` tooling, not live runs. See
> [Credentials & constraints](#credentials--honest-constraints).

---

## Table of contents
1. [Architecture](#architecture)
2. [The closed loop](#the-closed-loop)
3. [Packages & functionality](#packages--functionality)
4. [Key architectural decisions](#key-architectural-decisions)
5. [Use cases & workflows](#use-cases--workflows)
6. [CLI reference](#cli-reference)
7. [Testing & quality](#testing--quality)
8. [Credentials & honest constraints](#credentials--honest-constraints)
9. [Build timeline](#build-timeline)
10. [What's next](#whats-next)

---

## Architecture

Four cohesive packages under `src/`, each independently installed and CLI-driven,
sharing one venv and a common `.env`:

| Package | CLI | Responsibility |
|---------|-----|----------------|
| **etsyshop** | `etsyshop` | Core: product creation, pricing, listing SEO, both Etsy publish paths, image generation, orders/profit, the growth orchestrator |
| **trendscanner** | `trendscan` | Scan public sources (RSS, Google Trends, ecommerce JSON-LD) → normalized trend signals feeding the niche detector |
| **adsuite** | `adctl` | Organic posts (FB/IG/TikTok), paid campaigns (Meta/Google), A/B experiments |
| **shopkit** | `shopctl` | Shopify niche-store factory: catalog, brand, Merchant feed, pixel, profit-gated store creation |

```
                        PRODUCT ENGINE (etsyshop)
        trends ─► ideate ─► design+QC ─► price ─► listing SEO
                              │                        │
         ┌────────────────────┘                        └─────────────────┐
         ▼                                                                ▼
   ETSY (marketplace / organic)                         SHOPIFY niche stores (owned funnel)
   A: Printify owns listing (auto-fulfill)               shopkit: catalog, brand, Merchant
   B: we own listing (full SEO control)                  feed, Meta Pixel + Google tag
         │                                                                │
         └───────────────────► adsuite (organic + paid + A/B) ◄───────────┘
                          (paid → Etsy/Shopify; Google Shopping/PMax; pixel)
                                          │
                          PROFITABILITY BRAIN (net P&L: rev − COGS − fees − ad spend)
                                          │
                          GROWTH ORCHESTRATOR  →  scale winners / kill losers
                                          │
                          trendscanner feeds new niche candidates back in
```

Cross-cutting infra: `retry.py` (rate-limit backoff), `logging_setup.py`,
`doctor.py` (preflight), a FastAPI `dashboard/`, CI (`.github/workflows/ci.yml`),
and a `Dockerfile`.

---

## The closed loop

`etsyshop grow run` orchestrates the whole business in one cycle:

```
select in-season niches → ideate concepts → make (design+QC → price → publish)
   → advertise → measure (profit from orders) → decide (scale/hold/kill)
   → act (scale winners / deactivate losers) → promote profitable niche to its
   own Shopify store → repeat
```

- **Dry-run by default** (`grow run`) — real niche selection + profit decisions,
  simulated make/ads, free and offline.
- **`grow run --execute`** wires the real modules end-to-end (digital niches fully
  automatic; POD needs a catalog template).
- **Guardrails**: max new products/cycle, cumulative ad-spend cap, kill switch,
  halt-on-QC-failure.

---

## Packages & functionality

### etsyshop (core)
**Clients**
- `clients/printify.py` — `PrintifyClient`: shops, catalog (blueprints/providers/
  variants), image upload, create/publish product, `get_product`, orders,
  `create_order` + `send_to_production` (Architecture B fulfillment), CDN
  `download`; retry/backoff.
- `clients/etsy.py` — `EtsyClient`: OAuth2 **PKCE** login, listings/receipts reads,
  seller taxonomy nodes/properties, `update_listing` (PATCH), `update_listing_property`
  (PUT), `create_draft_listing`, `upload_listing_image`/`upload_listing_file`,
  shipping profiles, return policies, `update_listing_inventory`, `delete_listing`;
  401-refresh + retry/backoff.

**Products & listings**
- `models.py` — `ProductTemplate`, `Design`/`DesignManifest`, `DesignBrief`,
  `ProductConcept`, `OptimizedListing`, `ListingDraft`.
- `pipeline.py` — Phase 1: build Printify product payload, upload→create→publish.
- `optimize.py` — Phase 2: Claude generates Etsy-compliant SEO (≤140-char title,
  13 tags ≤20 chars, structured description, **mandatory AI-use disclosure**),
  normalized to Etsy's hard limits.
- `pricing.py` — fee-aware engine: `FeeSchedule` (US/UK/NL/FR), break-even,
  target-margin, **ad-safe floor**, charm/prestige rounding. Validated against the
  research playbook's worked example.
- `enrich.py` + `taxonomy.py` — set the Etsy **category + attributes** Printify's
  sync can't (overcomes the SEO gap); resolves `taxonomy_id` and maps attributes to
  valid value ids.
- `publisher.py` + `mockups.py` + `shopconfig.py` — **Architecture B**: create &
  own the Etsy listing (`createDraftListing` → relay Printify mockups / upload
  digital files → category+attributes → activate), auto-resolving shipping
  profile + return policy.
- `inventory.py` — multi-variant Etsy inventory (SKU = Printify variant for routing).
- `store.py` — persistent listing↔Printify-product mapping.
- `fulfill.py` — manual fulfillment bridge (Etsy receipt → Printify order, SKU-routed).
- `smoketest.py` — create one real draft listing, diff sent-vs-stored, delete it.

**Trends, ideation, planning**
- `trends.py` + `data/trends.json` — ranked, **seasonal** niche catalog + date-aware
  selector (peak > build > upcoming).
- `ideate.py` — niche → IP-safe `ProductConcept`s + design briefs (Claude).
- `engine.py` — campaign planner, `product_cost_from_printify`, `publish_plan`.

**Images**
- `imagegen.py` — pluggable `ImageProvider` seam: OpenAI GPT Image (raster) +
  Recraft (vector) + manual fallback; auto-selects by product type.
- `imageqc.py` — **Claude-vision QC** (flags text artifacts, watermarks, possible
  trademarks, anatomy errors).
- `imagestd.py` — print normalization (300 DPI RGBA PNG via Pillow).
- `design.py` — orchestrates brief → generate → QC → artifact.

**Money & growth**
- `analytics.py` — winner tracking (rank listings by units + revenue).
- `profit.py` — **profitability brain**: net-P&L ledger, scale/hold/kill decisions.
- `growth.py` — **orchestrator** `run_cycle` + guardrails + offline plan steps.
- `growth_live.py` — live wiring (`make_concept`, `build_live_steps`) for `--execute`.

**Infra** — `config.py`, `retry.py`, `logging_setup.py`, `doctor.py`,
`orders.py` (reconciliation), `dashboard/app.py` (FastAPI cockpit), `cli.py`.

### trendscanner
- `models.py` `TrendSignal`; `net.py` robots-aware polite fetch.
- `sources/`: `rss.py`, `google_trends.py` (official RSS endpoint), `ecommerce.py`
  (schema.org JSON-LD).
- `aggregate.py` — n-gram frequency ranking; `bridge.py` — map signals to existing
  niches + surface emerging-term candidates; `scan.py` + `trendscan` runner.

### adsuite
- `models.py` (Creative/Campaign/Metrics/Experiment), `config.py` (+ `channel_available`).
- `creative.py` — Claude ad/organic copy with FTC/ASA disclosure.
- `channels/organic.py` — Meta (FB photo + IG publish), TikTok Content Posting.
- `channels/paid.py` — Meta Ads (campaign→adset→ad), Google Ads (Search + PMax),
  insights normalization, `launch_shopping`.
- `experiment.py` — A/B engine: launch parallel variants, collect insights, **decide**
  winner (CPA/ROAS + min-sample + margin), **act** (scale winner / pause loser).
- `store.py`, `report.py`, `policy.py` (prohibited-claim + disclosure guardrails), `cli.py`.

### shopkit
- `client.py` — `ShopifyClient` (Admin GraphQL: products, variants, collections,
  pages, web pixel) + `DryRunShopifyClient`.
- `provision.py` — brand kit + niche collection + about page.
- `sync.py` — push optimized listings as Shopify products.
- `feed.py` — Google Merchant Center feed (unlocks Shopping/PMax).
- `pixel.py` — Meta/Google tag config.
- `store.py` — shop registry + honest manual go-live checklist.
- `gating.py` — **profit-gated** store creation (a niche earns a store once a product
  is profitable). `cli.py`.

---

## Key architectural decisions

1. **Architecture A vs B for Etsy publishing.** A = Printify owns the listing
   (free auto-fulfillment, weaker SEO control); B = we own it (full SEO, digital
   support, but we route orders). Chosen: **hybrid by product type** — A for
   physical POD where fulfillment automation wins; B for digital (which Printify
   can't publish at all) and where SEO control matters. At zero orders, optimize for
   discovery (B), defer the order router to a manual bridge.
2. **Listing enrichment.** Printify's sync omits category + attributes; we set them
   via the Etsy API after publish (they persist because Printify never re-syncs them).
3. **Image seam.** Claude can't generate images → a pluggable provider seam
   (OpenAI/Recraft/manual) with **Claude vision** as the QC gate.
4. **Profit-gated Shopify stores.** Owned-funnel stores unlock pixel/retargeting +
   Google Shopping/PMax, but a store-per-niche is costly — so stores are created
   **only for niches the profit brain validates**.
5. **Closed-loop orchestration with guardrails.** One `run_cycle` engine wires every
   stage behind injectable steps (fully testable offline) with spend/quantity caps
   and a kill switch.
6. **Honesty about gates.** Every external integration degrades to **dry-run** and is
   mock-tested; `doctor` reports exactly what's configured.

These were informed by five research reports: pricing playbook, AI design workflows,
growth/SEO handbook, listing-quality guide, and a seasonal niche report.

---

## Use cases & workflows

| Goal | Command(s) |
|------|-----------|
| See what's configured | `etsyshop doctor` |
| What's trending now | `etsyshop trends` · `trendscan sources.json` |
| Idea → art (with QC) | `etsyshop ideate --niche X` · `etsyshop design --niche X --slug Y` |
| Optimize a listing | `etsyshop optimize --template … --manifest … --slug …` |
| Fee-aware price | `etsyshop price --product-cost 5 --margin 0.45` |
| Publish (A: Printify-owned) | `etsyshop products create --publish --enrich` |
| Publish (B: we own listing) | `etsyshop publish pod …` · digital via `plan --publish` |
| Live-test Etsy writes | `etsyshop smoke` |
| Organic social posts | `adctl organic --slug … --image-url … --channel facebook …` |
| Paid campaign | `adctl paid --name … --landing-url … --daily-budget 5` |
| A/B two products | `adctl experiment --slug … --product-a … --product-b …` |
| True profit + decisions | `etsyshop profit` · `etsyshop winners` |
| Shopify niche store | `shopctl provision --niche …` · `shopctl sync …` · `shopctl feed --from …` |
| Should a niche get a store? | `shopctl gate` |
| **Run the whole loop** | `etsyshop grow run` (dry-run) · `etsyshop grow run --execute` |
| Order reconciliation | `etsyshop orders status` · fulfill: `etsyshop fulfill --receipt-id …` |
| Web cockpit | `etsyshop dashboard` |

See `docs/ONBOARDING.md` for the credentials + first-run runbook, and the per-area
backlogs: `docs/BACKLOG.md` (core), `docs/ADSUITE_BACKLOG.md`, `docs/GROWTH_BACKLOG.md`.

---

## CLI reference

- **`etsyshop`** — `doctor`, `connect-test`, `etsy login|whoami`, `printify shops`,
  `catalog blueprints|providers|variants`, `optimize`, `ideate`, `design`, `price`,
  `trends`, `products create`, `publish pod`, `listing taxonomy|enrich`, `plan`,
  `smoke`, `orders status`, `fulfill`, `winners`, `profit`, `grow run`, `dashboard`.
- **`trendscan`** — run a sources config → ranked trend feed.
- **`adctl`** — `organic`, `paid`, `experiment`, `report`.
- **`shopctl`** — `status`, `provision`, `sync`, `feed`, `gate`.

---

## Testing & quality
- **203 tests passing**, **ruff clean**. No network or billable calls in the suite —
  every external client is mock-tested (httpx mock transport / fake clients), and
  AI/image calls use injected fakes.
- **Fixture-pinned shape tests** (`tests/fixtures/` + `test_fixtures.py`) lock real
  Etsy/Printify/Meta/Google/Shopify response shapes through our parsers so they
  can't silently drift.
- **CI** runs ruff + pytest on push; **Dockerfile** ships the dashboard/scanner.

---

## Credentials & honest constraints
Set in `.env` (see `.env.example`); `etsyshop doctor` shows readiness.

| System | Effort to go live |
|--------|-------------------|
| **Anthropic** | Instant — Console + prepaid credits. Unlocks the whole AI brain. |
| **OpenAI / Recraft** | Instant — API keys for image generation. |
| **Printify** | Instant — Personal Access Token. |
| **Etsy** | Create app → **"Pending Personal Approval"** (Etsy reviews, ~days), then OAuth login. |
| **Meta (FB/IG)** | App Review + Business Verification for ads/publishing (days–weeks). |
| **TikTok** | Content Posting API **audit** (drafts-only until audited) + Marketing API. |
| **Google Ads** | Approved developer token + OAuth; Shopping/PMax needs the Shopify Merchant feed. |
| **Shopify** | Admin token on an existing store; billable store creation = Partner dev store + manual go-live. |

Until each is configured, that stage runs in dry-run and the code activates it
automatically once the credential is present.

---

## Build timeline
29 commits, grouped:
- **Phase 0–4** — foundation, clients, bulk creation, AI optimization, order
  reconciliation, dashboard.
- **Trend engine** — fee-aware pricing, seasonal niche catalog, ideation, planner.
- **Etsy enrichment** + **Architecture B** (own the listing).
- **I1–I9** — image seam + Claude QC, trend→publisher wiring, smoke harness,
  trendscanner subproject (RSS/Google/ecommerce + aggregator + bridge), real
  Printify costs + retry/backoff, shipping/return resolve + winner tracking,
  multi-variant inventory + logging, print normalization + CI + Dockerfile.
- **AI1–AI5** — adsuite: foundation, organic, paid, A/B experiment engine, ops.
- **GI1–GI6** — growth platform: profit brain, orchestrator, shopkit Shopify factory
  (client→provision→sync→feed/pixel→gating→adsuite integration), verification/doctor.
- **Live wiring** — `grow run --execute` end-to-end.

---

## What's next
- Connect Anthropic + Printify + Etsy (once approved) → run `grow run --execute
  --max-products 1 --no-ads` as the first safe live cycle.
- Add a **POD ProductTemplate** (real catalog ids) so physical products also publish
  fully in `--execute`.
- Schedule the loop daily via a cloud routine (`/schedule`) once credentials are in.
- Submit Meta/TikTok/Google/Shopify for approval in parallel; they activate
  automatically as tokens land.
