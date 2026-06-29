# CLAUDE.md

Operating guide for agents working in this repo. For the full narrative
(architecture, decisions, use cases) read `docs/PROJECT_OVERVIEW.md`; for the
command/workflow cheat sheet see `docs/USAGE.md`; for credentials/first-run see
`docs/ONBOARDING.md`.

## What this is
A trend-driven Etsy/Shopify print-on-demand automation platform: detect trends →
create products → optimize listings → price → publish → advertise → measure profit
→ scale winners, optionally as one self-running loop (`etsyshop grow run`).

## Layout (src-layout, 4 installed packages)
- `src/etsyshop/` — core (clients, products, pricing, listings, images, profit,
  growth orchestrator). CLI: `etsyshop`.
- `src/trendscanner/` — trend signal scanner (RSS/Google/ecommerce). CLI: `trendscan`.
- `src/adsuite/` — ads: organic, paid, A/B experiments. CLI: `adctl`.
- `src/shopkit/` — Shopify niche-store factory. CLI: `shopctl`.
- `docs/` — `PROJECT_OVERVIEW.md`, `ONBOARDING.md`, and three `*_BACKLOG.md` files.
- `tests/` — pytest; `tests/fixtures/` pins real API response shapes.

## Commands
```bash
# Setup — system python3 is 3.10 (too old); use 3.13
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,dashboard,images]"

pytest -q                     # full suite — must stay green, no network/billable calls
ruff check src tests          # lint — must stay clean (CI runs both)
etsyshop doctor               # what's configured vs missing
```
CLIs after install: `etsyshop`, `trendscan`, `adctl`, `shopctl`.

## Conventions you MUST follow

**Degrade-to-dry-run.** Every external integration has a factory
(`make_client`, `make_channel`, `make_paid_channel`, `select_provider`,
`build_*_steps`) that returns a real client when creds exist (gated by
`settings.require(...)` / `*_available(...)`) and a **DryRun stub / skip** otherwise.
New integrations follow this pattern — never hard-require a credential.

**Seam + injection for testability.** Heavy/external steps are injectable
(provider objects, `*_fn` callables, `http=` clients). Tests pass fakes; nothing
hits the network or spends money. Examples: `ImageProvider`, `OrganicChannel`,
`PaidChannel`, `ShopifyClient`, `GrowthSteps`, `build_live_steps(...)` deps.

**Testing rules.**
- Mock HTTP: clients holding `self._http` → swap an `httpx.Client(transport=httpx.MockTransport(...))`; clients calling module-level `httpx` → `monkeypatch.setattr(mod.httpx, "post"/"request", fake)`.
- Don't call `raise_for_status()` on hand-built `httpx.Response` (no bound request) — code checks `resp.status_code >= 400` instead.
- Claude calls: inject a fake client whose `.messages.parse(**kw)` returns
  `SimpleNamespace(parsed_output=<pydantic>)`; `monkeypatch.setattr(settings, "anthropic_api_key", "test")`.
- Image tests must force manual mode (`monkeypatch.setattr(settings, "image_provider", "manual")`) so an exported `OPENAI_API_KEY` can't trigger a real (billable) call.

**HTTP clients.** Retry 429/5xx with backoff via `etsyshop/retry.py` (`_sleep`
injectable). Raise typed errors (`PrintifyError`, `EtsyError`, `ShopifyError`).

**External API shapes (verified, pinned in `tests/fixtures/`):**
- Etsy: `updateListing` = **PATCH** form-encoded; `updateListingProperty` = **PUT**;
  `createDraftListing` = POST form; arrays passed as Python lists (httpx repeats keys).
- Shopify: Admin **GraphQL**, always surface `userErrors`.
- Meta Graph / Google Ads `googleAds:mutate` / TikTok content-posting shapes are
  pinned via normalize/parse tests. If you touch a request shape, update the fixture.

**Claude/Anthropic code.** Use the official `anthropic` SDK,
`client.messages.parse(model=settings.anthropic_model, output_format=<pydantic>)`.
Model is **`claude-opus-4-8`** — do not downgrade. For any new Claude feature,
consult the bundled `claude-api` skill before writing SDK code.

**State & data.** Runtime state in `.state/` (git-ignored: listings, shops,
adsuite, growth, `.tokens.json`); generated art in `designs/art|briefs/`
(git-ignored). Versioned data (e.g. `data/trends.json`) is tracked — don't
git-ignore `data/`.

**Models.** Pydantic v2 in `etsyshop/models.py`, `adsuite/models.py`,
`trendscanner/models.py`, `shopkit/*`. Settings via `pydantic-settings`
`BaseSettings` reading `.env`.

**Commits.** End every commit message with:
```
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
```

## Workflow for changes
1. Implement the smallest coherent slice.
2. Add tests that mock all external calls; run `pytest -q` (all green) and
   `ruff check src tests` (clean) — fix `E402` by keeping module-level assignments
   after imports.
3. Commit with the co-author trailer.
4. If working a backlog (`docs/*_BACKLOG.md`), check off the story and append an
   iteration-log line. The `loop` skill drives these autonomously, one story per
   iteration.

## Gotchas
- **Claude can't generate images** — `imagegen.py` uses third-party providers
  (OpenAI/Recraft); `imageqc.py` uses Claude *vision* for QC.
- **Two Etsy publish paths**: A = Printify owns the listing (auto-fulfill, weaker
  SEO); B = `publisher.py`, we own it (full SEO, digital). Printify can't set Etsy
  category/attributes → `enrich.py` fills them post-publish.
- **Live verification gap**: external shapes are unit/fixture-tested but most aren't
  run against production APIs. Use `etsyshop smoke` / `etsyshop doctor` to validate
  with real creds; never weaken the "no billable calls in tests" rule to compensate.
- **Etsy onboarding**: new apps sit in "Pending Personal Approval"; OAuth needs the
  callback URL registered on the app *and* `ETSY_REDIRECT_URI` matching it.
- **`grow run`** is dry-run by default; `--execute` runs real modules (digital fully
  automatic, POD needs a `ProductTemplate` with real catalog ids).
