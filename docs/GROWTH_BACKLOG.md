# Growth platform backlog — orchestrator, profit brain, Shopify stores, verification

Source of truth for the growth build loop. Each iteration: pick the next
unchecked story (top to bottom), implement with tests, run the full pytest
suite, commit, check it off.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

## Why
Connect the existing toolbox (etsyshop, trendscanner, adsuite) into a
self-running, profit-optimizing engine, and add owned-funnel Shopify niche
stores to maximize the paid-ads platform.

## Prerequisites & honest constraints
- Profit brain unifies COGS (Printify), marketplace fees (Etsy/Shopify), ad
  spend (adsuite), revenue (orders) into net contribution margin.
- Shopify Admin API automates catalog/brand/feed/pixel on an EXISTING store.
  Billable production-store creation is not a public API — use Partner dev
  stores where possible + a documented manual go-live step.
- A dedicated store is created only when a niche/product is VALIDATED by the
  profit brain (winner + positive margin). Cheaper fallback: one brand store
  with per-niche collections.
- Everything mock-tested, dry-run without credentials.

---

## Epic P — Profitability brain
- [x] **P.1** Unified P&L model + calculator: net = revenue − COGS − platform
  fees − ad spend − returns reserve; per product/listing/campaign. _AC: tested._
- [x] **P.2** Ledger collectors: normalize Etsy receipts + Shopify orders
  (revenue), adsuite insights (ad spend), Printify (COGS) into one ledger.
  Injectable/mocked. _AC: tested._
- [x] **P.3** Ranking + decisions: rank by contribution margin; classify
  scale / hold / kill with thresholds. _AC: scale/hold/kill cases tested._
- [x] **P.4** CLI `etsyshop profit` report; emit scale/kill signals consumable
  by the orchestrator and adsuite. _AC: report assembly tested._

## Epic G — Growth orchestrator (closed loop)
- [x] **G.1** Pipeline state machine: stages (scan→ideate→design→price→publish→
  advertise→measure→decide→act), each idempotent + resumable + persisted. _AC: tested._
- [x] **G.2** `run_cycle()` wiring existing modules via injectable steps; dedupe
  against state. _AC: tested with mock steps._
- [x] **G.3** Guardrails: max new products/day, max ad spend/day, halt on
  QC/policy fail, global kill switch. _AC: guardrail enforcement tested._
- [x] **G.4** Act on decisions: scale winners (clone variations + raise budget),
  kill losers (pause ads + deactivate listing). _AC: tested._
- [x] **G.5** CLI `etsyshop grow run` (dry-run default) + schedule/loop hook for
  continuous operation. _AC: cycle runs end-to-end with mocks._

## Epic S — Shopify niche-store factory (`shopkit` subproject)
- [ ] **S.1** `shopkit` package + ShopifyClient (Admin GraphQL): products,
  variants, collections, pages, navigation, publications; dry-run + mock-tested. _AC._
- [ ] **S.2** Store provisioner: brand a niche store (palette/fonts/policies/SEO)
  + niche collection + home content from the niche catalog. _AC: tested._
- [ ] **S.3** Product sync: push validated products (reuse designs/mockups/listing
  copy from etsyshop) to Shopify; link Printify fulfillment. _AC: payload tested._
- [ ] **S.4** Google Merchant Center feed generation + Meta Pixel / Google tag
  config (unlock Shopping/PMax + conversion tracking). _AC: feed/pixel tested._
- [ ] **S.5** Partner dev-store creation where possible + documented manual
  production go-live; store registry/state. _AC: registry tested._
- [ ] **S.6** Profit gating: provision/promote a dedicated store only when the
  niche/product clears the profit threshold (Epic P). _AC: gate tested._
- [ ] **S.7** adsuite integration: paid campaigns target Shopify URLs; add a
  Google Shopping/PMax channel; pixel conversions flow into the profit ledger. _AC._
- [ ] **S.8** CLI `shopctl` (provision | sync | feed | status). _AC: smoke-tested._

## Epic V — Live verification & onboarding
- [ ] **V.1** `etsyshop doctor`: check every credential/config; report
  ready/missing per system (Etsy, Printify, Anthropic, image, ads, Shopify). _AC: tested._
- [ ] **V.2** Safe per-system smoke tests (Etsy draft, Printify, image gen, ad
  dry-run, Shopify) behind confirmation. _AC: harness tested with mocks._
- [ ] **V.3** Recorded-fixture (VCR-style) integration tests pinning live request
  shapes so they don't silently drift. _AC: at least one per external API._
- [ ] **V.4** Onboarding doc: credentials + approvals + first-run runbook.

---

## Iteration log
- (build loop appends here)
- GI1: Epic P profit brain — ProductPnL (net/margin), platform-fee estimate, build_ledger, revenue/units from receipts, classify scale/hold/kill, rank + decisions, 'etsyshop profit' CLI.
- GI2: Epic G growth orchestrator — run_cycle engine (select->ideate->make->advertise->measure->decide->act), Guardrails (max products, ad-spend cap, kill switch, QC-halt), dedupe, build_plan_steps offline dry-run, 'etsyshop grow run' CLI.
