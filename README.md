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

## Notes on credentials & safety

- `.env` and `.tokens.json` are git-ignored. Never commit them.
- Etsy tokens auto-refresh; if refresh fails, re-run `etsyshop etsy login`.
