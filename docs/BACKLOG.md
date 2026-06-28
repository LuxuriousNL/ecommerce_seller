# etsyshop — autonomous build backlog

Source of truth for the overnight self-paced loop. Each iteration: pick the next
unchecked story, implement with tests, run the full suite, commit, check it off.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Epic 1 — Trend engine → publisher (end-to-end)
- [x] **E1.1** As an operator, `plan --publish` turns the campaign plan into live
  listings: digital niches via the B publisher (`createDraftListing` + file upload),
  POD niches via `publish pod`. _AC: dry-run prints; `--publish` creates; dedupe via store._
- [x] **E1.2** Digital-product draft builder (`draft_for_digital`) from concept +
  optimized listing + pricing + niche taxonomy/attributes. _AC: unit-tested._
- [x] **E1.3** Plan persistence + dedupe: skip concepts whose slug already in
  `.state/listings.json`. _AC: tested._

## Epic 2 — Image-generation seam
- [x] **E2.1** `ImageProvider` protocol + factory (auto/openai/recraft/manual),
  degrades to manual when no key. _AC: provider selection unit-tested._
- [x] **E2.2** OpenAI GPT Image provider (raster, transparent bg). _AC: request
  shaping tested via mocked httpx._
- [x] **E2.3** Recraft provider (vector/SVG for sticker/tee niches). _AC: same._
- [x] **E2.4** Manual provider: write the design brief to a file for external gen.

## Epic 3 — Image QC + smoke tests
- [x] **E3.1** Claude-vision QC gate (`qc_image`): flag unintended text,
  watermarks, possible trademarks, anatomy errors; hold back failures. _AC: tested
  with mocked Anthropic client._
- [x] **E3.2** `design` orchestrator: brief → generate → QC → save artifact +
  CLI `design`. _AC: manual/ready/qc_failed/error paths tested._
- [ ] **E3.3** B live-smoke-test harness: a guarded script that, given real creds,
  creates ONE draft listing (no activate) and reports field-by-field what stuck —
  the manual confirmation step for the unverified Etsy write calls.

## Epic 4 — trendscanner subproject (separate package)
> Ethics: respect robots.txt + site ToS; prefer official APIs + RSS + sitemaps;
> rate-limit; cache; no aggressive scraping. Pluggable sources.
- [ ] **E4.1** Subproject scaffold `trendscanner/` (own package, shared venv):
  `TrendSignal` model (source, term, category, score, observed_at, url).
- [ ] **E4.2** RSS/news source adapter (fashion/gifting/news feeds) → signals.
- [ ] **E4.3** Google Trends adapter (pytrends or public endpoint) → signals.
- [ ] **E4.4** Ecommerce "new/bestseller" adapter (sitemap/JSON-LD, robots-aware).
- [ ] **E4.5** Aggregator: normalize + dedupe + score signals into a feed file.
- [ ] **E4.6** Bridge into etsyshop: map signals → niche keywords / new niche
  candidates; `trends --signals` surfaces emerging terms. _AC: tested with fixtures._

## Epic 5 — Improvements (brought in)
- [ ] **E5.1** Real Printify variant cost lookup → replace `estimate_product_cost`.
- [ ] **E5.2** Client resilience: retry + backoff + rate-limit handling for Etsy
  (10/s, 10k/day) and Printify (200/30min publish). _AC: tested._
- [ ] **E5.3** Multi-variant Etsy listings in B (`updateListingInventory`) +
  variant_map population for accurate fulfillment routing.
- [ ] **E5.4** Shipping-profile + return-policy auto-resolution before activate.
- [ ] **E5.5** Winner tracking: read orders, rank listings, feed back into the
  planner to double down on sellers.
- [ ] **E5.6** Print-standard normalization (300 DPI, sRGB, PNG/transparent) via
  optional Pillow extra.
- [ ] **E5.7** Structured logging across the pipeline.
- [ ] **E5.8** CI (GitHub Actions) running `pytest` + ruff on push.
- [ ] **E5.9** Dockerfile for the dashboard + a scanner runner.
- [ ] **E5.10** `dashboard`: add trends/plan/design panels.

---

## Iteration log
- I1: backlog created; Epic 2 (image seam) + E3.1/E3.2 implemented with tests.
- I2: Epic 1 — draft_for_digital, local-image upload, dedupe, publish_plan + plan --publish wiring.
