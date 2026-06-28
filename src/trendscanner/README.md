# trendscanner

A **separate subproject** (own package, shared repo/venv) that scans public
sources for emerging terms and emits normalized `TrendSignal`s that feed
etsyshop's trend detector.

## Design
```
sources/ (rss, google-trends, ecommerce) ──► TrendSignal[] ──► aggregate ──► feed.json
                                                                    │
                                                          etsyshop bridge: signals
                                                          -> niche keywords / candidates
```

## Ethics & compliance (non-negotiable)
- Respect `robots.txt` and each site's Terms of Service.
- Prefer **official APIs**, **RSS/Atom feeds**, and **sitemaps** over HTML scraping.
- Rate-limit and cache; identify with a clear User-Agent.
- No aggressive crawling, no bypassing access controls, no PII collection.

## Status
- [x] E4.1 scaffold + `TrendSignal` model
- [ ] E4.2 RSS source adapter
- [ ] E4.3 Google Trends adapter
- [ ] E4.4 ecommerce new/bestseller adapter (robots-aware)
- [ ] E4.5 aggregator (normalize + dedupe + score)
- [ ] E4.6 etsyshop bridge
