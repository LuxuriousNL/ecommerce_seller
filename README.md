# etsyshop

Automate an Etsy print-on-demand shop via **Printify**: bulk product creation,
AI listing optimization, and order operations.

## How it works

You create products in **Printify** (programmatically), Printify's native Etsy
integration publishes them as Etsy listings and **auto-fulfills orders**. This
tool adds the automation + AI layer on top:

- **Phase 0** (this) — foundation: config, Printify + Etsy API clients, `connect-test`.
- **Phase 1** — bulk product creation from designs + reusable templates.
- **Phase 2** — AI listing optimization with Claude (titles, 13 tags, descriptions).
- **Phase 3** — order ops: read orders, reconcile fulfillment, alert on exceptions.

## Setup

### 1. Install

```bash
cd /Users/alberto/etsyshop
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Credentials

```bash
cp .env.example .env
```

**Printify token** — Printify → Account → **Connections** → *Generate* a
Personal Access Token. Paste into `PRINTIFY_API_TOKEN`.

**Connect Printify → Etsy** (one-time, in the Printify dashboard): Printify →
**My stores** → *Add new store* → **Etsy** → authorize. This is what makes
publishing and auto-fulfillment work.

**Etsy app** — https://www.etsy.com/developers/your-apps → create an app. Copy
the **Keystring** into `ETSY_API_KEY`. Add `http://localhost:8080/callback` as a
**redirect URI** on the app. New apps have personal access immediately; commercial
scale may require requesting production access.

### 3. Discover your shop ids

```bash
etsyshop printify shops      # copy the id into PRINTIFY_SHOP_ID
etsyshop etsy login          # opens a browser for OAuth; stores .tokens.json
etsyshop etsy whoami         # confirm authorization
```

### 4. Verify everything

```bash
etsyshop connect-test
```

You should see green OK lines for both Printify and Etsy.

## Usage

### Phase 1 — build a product template, then bulk-create

Templates reference Printify catalog ids. Discover them, then edit
`templates/tshirt.example.json` (the ids in it are placeholders):

```bash
etsyshop catalog blueprints --search "tee"     # find a blueprint_id
etsyshop catalog providers 6                   # print providers for that blueprint
etsyshop catalog variants 6 99                 # variant ids (sizes/colors)
```

Point a design manifest at your artwork (`designs/manifest.example.json` shows
both local `image_path` and remote `image_url`), then create products:

```bash
# Create drafts in Printify (no Etsy publish yet)
etsyshop products create --template templates/tshirt.example.json \
                         --manifest designs/manifest.example.json

# Create AND publish to Etsy, with AI-optimized listings (Phases 1+2)
etsyshop products create --template templates/tshirt.example.json \
                         --manifest designs/manifest.example.json \
                         --optimize --publish
```

### Phase 2 — preview AI listing optimization

Requires `ANTHROPIC_API_KEY`. Generates an Etsy-compliant title (≤140 chars), 13
tags (≤20 chars each), description, and materials for one design — no writes:

```bash
etsyshop optimize --template templates/tshirt.example.json \
                  --manifest designs/manifest.example.json \
                  --slug retro-sunset-surf
```

### Phase 3 — monitor orders

Printify auto-fulfills synced Etsy orders; this reconciles both sides and flags
anything stuck or unmatched:

```bash
etsyshop orders status
```

### Phase 4 — web dashboard

A FastAPI control plane over the same logic, with a connections panel, product
list, order reconciliation, and an interactive AI optimizer.

```bash
pip install -e '.[dashboard]'
etsyshop dashboard            # http://127.0.0.1:8000
```

## Development & tests

The suite mocks the HTTP clients (and Claude), so it runs offline with no
credentials:

```bash
pip install -e '.[dev,dashboard]'
pytest -q
```

Coverage: payload building, Etsy-limit normalization, the create/publish
pipeline (happy + error paths), order reconciliation, the Printify/Etsy HTTP
clients (via `httpx` mock transport), and the dashboard API.

## Notes on credentials & safety

- `.env` and `.tokens.json` are git-ignored. Never commit them.
- Etsy tokens auto-refresh; if refresh fails, re-run `etsyshop etsy login`.
