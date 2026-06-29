# adsuite — advertisement suite backlog

Source of truth for the adsuite build loop. Each iteration: pick the next
unchecked story (top to bottom), implement with tests, run the full pytest
suite, commit, check it off.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

## Goals (user's three capabilities)
1. Organic traffic: take designs/mockups → posts on Facebook, Instagram, TikTok.
2. Paid ads: campaigns on Google Ads and Facebook/Instagram.
3. A/B: run two products as parallel Google+FB campaigns, compare, double down on
   the winner and discard the loser.

## Prerequisites & limitations (external, not blockers for building)
- Meta paid = Marketing API; organic = Graph API. Needs a Business app + App
  Review (`ads_management`, `pages_manage_posts`, `instagram_content_publish`),
  an ad account, a FB Page, and a linked IG Business/Creator account.
- TikTok = Marketing API + Content Posting API (audited app; may post to drafts).
- Google Ads = approved developer token + OAuth + manager account; no Merchant
  feed for Etsy-only, so use Search/Demand Gen to listing URLs.
- All adapters are built behind a seam, mock-tested for request shaping, and
  **degrade to dry-run** when credentials are absent. Live verification needs creds.
- Copy generation includes FTC/ASA paid-ad disclosure and platform policy guards.

---

## Epic A1 — Foundation & creative
- [ ] **A1.1** `adsuite` package scaffold (own installed package, shared venv) +
  core models: `Creative`, `Campaign`, `AdSet`, `Ad`, `Metrics`, `Experiment`,
  `ChannelResult`. _AC: models + slugify tested._
- [ ] **A1.2** `CreativeBuilder`: from a design/mockup path/url + listing context
  → platform creatives (aspect ratios 1:1, 4:5, 9:16) + Claude-generated copy
  (organic caption + hashtags per platform; paid ad headline/primary text with
  FTC/ASA disclosure). _AC: copy builder tested with a mocked Anthropic client._
- [ ] **A1.3** Config + credentials: Meta (app token, page id, IG business id),
  TikTok (token, advertiser id), Google Ads (dev token, customer id, OAuth) in
  config + `.env.example`; `channel_available(name)` detection. _AC: tested._

## Epic A2 — Organic posting (capability 1)
- [ ] **A2.1** `OrganicChannel` protocol (`post(creative) -> PostResult`) + factory
  that returns a `DryRunChannel` when creds are missing. _AC: tested._
- [ ] **A2.2** Meta organic adapter: FB Page feed post + IG content publish
  (create media container → publish). _AC: request shaping tested via mock httpx._
- [ ] **A2.3** TikTok organic adapter: Content Posting API (init → upload → publish;
  draft fallback). _AC: request shaping tested._
- [ ] **A2.4** Organic orchestrator + CLI `adctl organic` (post one creative to
  selected channels, dry-run by default) + state record. _AC: orchestrator tested._

## Epic A3 — Paid campaigns (capability 2)
- [ ] **A3.1** `PaidChannel` protocol: `create_campaign`, `create_adset`,
  `create_ad`, `pause`, `set_budget`. _AC: tested._
- [ ] **A3.2** Meta Ads adapter: campaign (objective OUTCOME_TRAFFIC) → ad set
  (budget, targeting, optimization) → ad (creative). _AC: request shaping tested._
- [ ] **A3.3** Google Ads adapter: Search/Demand Gen campaign → ad group → ad to a
  listing URL (developer-token note). _AC: request shaping tested._
- [ ] **A3.4** Paid orchestrator + CLI `adctl paid` with budget guard
  (max daily spend) + state. _AC: budget guard + orchestration tested._

## Epic A4 — A/B experiment & decision (capability 3)
- [ ] **A4.1** `Experiment` model: two variants (product/creative), channels,
  budget split, objective, decision rule (metric, min_spend, min_conversions,
  margin). _AC: model + validation tested._
- [ ] **A4.2** Launch: create parallel campaigns per variant per channel; record
  ids in state. _AC: tested with mock channels._
- [ ] **A4.3** Insights collection: pull per-campaign metrics from each channel,
  normalize to `Metrics` (impressions, clicks, CTR, spend, conversions, CPA,
  ROAS). _AC: normalization tested._
- [ ] **A4.4** `DecisionEngine`: pick winner by rule (e.g. lower CPA / higher ROAS)
  with a min-sample guard that returns "inconclusive" until thresholds met.
  _AC: winner / loser / inconclusive cases tested._
- [ ] **A4.5** Act on decision: scale winner budget, pause/discard loser, record
  outcome; CLI `adctl experiment run|status|decide`. _AC: act-on-decision tested._

## Epic A5 — Ops & integration
- [ ] **A5.1** adsuite state store (campaigns/experiments JSON, git-ignored).
- [ ] **A5.2** etsyshop bridge: source creatives from the listings store + design
  artifacts; feed experiment winners back to the product planner. _AC: tested._
- [ ] **A5.3** Report: `adctl report` summarizing campaigns/experiments + an
  optional dashboard panel. _AC: report assembly tested._
- [ ] **A5.4** CI + Dockerfile + logging coverage for adsuite; ruff clean.
- [ ] **A5.5** Policy guardrails: FTC/ASA disclosure in paid copy, platform
  content checks (no prohibited claims), surfaced before publish. _AC: tested._

---

## Iteration log
- (build loop appends here)
