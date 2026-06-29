# USAGE — tools & workflows cheat sheet

How to use every CLI and workflow. Architecture lives in
[`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md); credentials in
[`ONBOARDING.md`](ONBOARDING.md); conventions in [`../CLAUDE.md`](../CLAUDE.md).

Four CLIs: **`etsyshop`** (core), **`trendscan`** (scraper), **`adctl`** (ads),
**`shopctl`** (Shopify). Everything runs **dry-run** until the relevant credential
is set — `etsyshop doctor` shows readiness.

## Setup (once)
```bash
cd <repo> && source .venv/bin/activate          # Python 3.13 venv
pip install -e ".[dev,dashboard,images]"
cp .env.example .env                              # add keys as you get them
etsyshop doctor                                   # what's configured vs missing
```

## A. Status
```bash
etsyshop doctor            # readiness across every integration
etsyshop doctor --smoke    # + safe read-only checks on ready systems
```

## B. Discover trends
```bash
etsyshop trends                       # in-season niches (peak > build > upcoming)
etsyshop trends --kind digital        # filter by type (pod|digital|physical)
trendscan data/sources.example.json out/trend-feed.json   # scrape live sources -> ranked feed
```
Edit `data/sources.example.json` (list of `{kind: rss|google_trends|ecommerce, target, category}`)
to point at your own feeds. Robots-aware; needs internet.

## C. Create a product (make pipeline)
```bash
etsyshop ideate --niche halloween-svg --count 3                     # niche -> concepts (Claude)
etsyshop design --niche halloween-svg --slug ghost                 # concept -> art + Claude-vision QC
etsyshop optimize --template templates/tshirt.example.json \
                  --manifest designs/manifest.example.json --slug retro-sunset-surf
etsyshop price --product-cost 5 --margin 0.45 --country US         # fee-aware price
```
Catalog discovery for POD templates:
`etsyshop catalog blueprints --search tee` → `catalog providers <id>` → `catalog variants <bp> <pp>`.

## D. Publish to Etsy
```bash
# A — Printify owns the listing (auto-fulfills); enrich category/attributes after
etsyshop products create --template … --manifest … --publish --enrich
# B — we own the listing (full SEO; required for digital)
etsyshop publish pod --template … --manifest … --shipping-profile-id 123 --activate
# Verify Etsy writes safely (creates one draft, checks fields, deletes it)
etsyshop smoke
# Enrich an existing listing manually
etsyshop listing taxonomy --search Ornaments
etsyshop listing enrich --listing-id 123 --taxonomy Ornaments \
                        --tag "family ornament" --attr Occasion=Christmas
```

## E. Advertise (`adctl`)
```bash
adctl organic --slug ghost --image-url https://cdn/x.png --caption "Spooky season" --hashtag halloween
adctl paid --name ghost-test --landing-url https://etsy.com/listing/123 --daily-budget 5
adctl experiment --slug tee-vs-mug --product-a tee --url-a <url> --product-b mug --url-b <url>
adctl report
```

## F. Measure & decide
```bash
etsyshop orders status                      # reconcile Etsy <-> Printify fulfillment
etsyshop winners                            # rank listings by sales
etsyshop profit                             # net-profit P&L + scale/hold/kill
etsyshop fulfill --receipt-id 9001 --send   # (Architecture B) route an order to Printify
```

## G. Shopify niche stores (`shopctl`)
```bash
shopctl status                              # connected vs dry-run
shopctl gate                                # is a niche profitable enough for its own store?
shopctl provision --niche halloween-svg     # brand + collection + about page
shopctl sync --title "Retro Tee" --tag retro --product-type "T-Shirt"
shopctl feed --from products.json --out out/merchant-feed.tsv   # Google Shopping/PMax feed
```

## H. The closed loop
```bash
etsyshop grow run                                          # dry-run plan (free, offline)
etsyshop grow run --execute --max-products 1 --no-ads      # safest first REAL cycle (1 digital product)
etsyshop grow run --execute --max-products 3 --max-ad-spend 15 --margin 0.45   # widen guardrails
```
Cycle: select niches → make → advertise → measure profit → scale winners / kill losers.
Guardrails: `--max-products`, `--max-ad-spend`, `--kill-switch`, halt-on-QC-failure.

## I. The console (web dashboard)
```bash
etsyshop dashboard            # http://127.0.0.1:8000  (--host/--port to change)
```
Panels: Connections · Trends now (offline) · Products · Orders · AI optimizer.

## J. Run continuously
```bash
/schedule every morning at 9am etsyshop grow run --execute --max-products 3 --yes   # cloud cron
/loop etsyshop grow run --execute --max-products 3 --yes                            # this session only
```

## Typical first run
1. `etsyshop doctor` → add **Anthropic** + **OpenAI** keys.
2. `etsyshop ideate --niche halloween-svg` → `etsyshop design --niche halloween-svg --slug ghost`.
3. Add **Printify** + **Etsy** (once approved) → `etsyshop etsy login` → `etsyshop smoke`.
4. `etsyshop grow run --execute --max-products 1 --no-ads` → verify the listing on Etsy.
5. Widen guardrails; layer in ads + Shopify as approvals land; `etsyshop profit` to steer.
