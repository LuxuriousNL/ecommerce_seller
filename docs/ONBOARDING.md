# Onboarding — credentials, approvals, first run

Everything runs **offline in dry-run** without credentials. Add creds to `.env`
(copy `.env.example`) to make each integration live. Run `etsyshop doctor` any
time to see what's configured.

## 1. Install
```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,dashboard,images]"
pytest -q          # full suite, no creds needed
etsyshop doctor    # what's configured vs missing
```

## 2. Credentials by system

| System | Env vars | Notes / approval |
|--------|----------|------------------|
| **Etsy** | `ETSY_API_KEY`, then `etsyshop etsy login` | App at etsy.com/developers; add `http://localhost:8080/callback` redirect. New apps = personal access; commercial scale may need review. |
| **Printify** | `PRINTIFY_API_TOKEN`, `PRINTIFY_SHOP_ID` | Account → Connections → Personal Access Token. Connect Printify→Etsy in their dashboard for Architecture A auto-fulfillment. |
| **Anthropic** | `ANTHROPIC_API_KEY` | Powers listing SEO, ideation, image QC, ad copy. |
| **Images** | `OPENAI_API_KEY` and/or `RECRAFT_API_KEY` | OpenAI = raster; Recraft = vector. Without either, design falls back to writing a brief. |
| **Meta (FB/IG)** | `META_ACCESS_TOKEN`, `META_PAGE_ID`, `META_IG_USER_ID`, `META_AD_ACCOUNT_ID` | Business app + **App Review** (`ads_management`, `pages_manage_posts`, `instagram_content_publish`). IG must be Business/Creator linked to the Page. |
| **TikTok** | `TIKTOK_ACCESS_TOKEN`, `TIKTOK_ADVERTISER_ID` | Marketing + Content Posting API (**audited app**; may post to drafts). |
| **Google Ads** | `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_CUSTOMER_ID`, `GOOGLE_ADS_REFRESH_TOKEN`, `GOOGLE_ADS_CLIENT_ID`, `GOOGLE_ADS_CLIENT_SECRET` | **Approved developer token** + OAuth. Shopping/PMax needs a Merchant feed (use a Shopify store). |
| **Shopify** | `SHOPIFY_SHOP_DOMAIN`, `SHOPIFY_ADMIN_TOKEN`, `SHOPIFY_API_VERSION` | Admin API automates catalog/feed/pixel on an existing store. Billable store creation = Partner dev store + manual go-live (`shopkit/store.py` checklist). |

## 3. First-run runbook (recommended order)
1. **Verify shapes (no creds):** `pytest -q` and skim `git log`.
2. **Anthropic only:** `etsyshop optimize …`, `etsyshop ideate --niche …`, `etsyshop design --niche … --subject …`.
3. **Printify token:** `etsyshop printify shops`, `etsyshop catalog blueprints`.
4. **Etsy live smoke:** `etsyshop smoke` — creates one draft listing, verifies what stuck, deletes it.
5. **Pricing/trends (no creds):** `etsyshop price …`, `etsyshop trends`, `etsyshop grow run` (dry-run plan).
6. **Ads (dry-run):** `adctl organic …`, `adctl paid …`, `adctl experiment …`.
7. **Shopify (dry-run):** `shopctl status`, `shopctl provision --niche …`, `shopctl sync …`.
8. **Profit + decisions:** `etsyshop profit`, `etsyshop winners` (once you have orders).

## 4. The closed loop
`etsyshop grow run` ties it together: in-season niches → make → advertise →
measure profit → scale winners / kill losers. A niche that proves profitable is
promoted to its own Shopify store (`shopctl`), where Google Shopping/PMax + the
pixel maximize the ad platform. Schedule it with `/loop` or a cron routine.
