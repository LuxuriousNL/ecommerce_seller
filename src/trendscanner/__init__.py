"""trendscanner — a separate subproject that scans public sources (fashion,
gifting, news, ecommerce) for emerging terms and emits normalized TrendSignals
to feed etsyshop's trend detector.

Ethics: respect robots.txt and site ToS; prefer official APIs, RSS, and
sitemaps; rate-limit; cache. No aggressive scraping.
"""

__version__ = "0.1.0"
