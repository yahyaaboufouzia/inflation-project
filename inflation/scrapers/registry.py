"""Map a site name to the scraper that handles it."""
from __future__ import annotations

from ..config import SiteCfg
from .base import BaseScraper
from .demo import DemoScraper
from .static import StaticScraper

# Real static sites reuse StaticScraper and differ only by their sites.yaml
# entry (selector, delay, ...). Sites that need JavaScript would register a
# Playwright-based class here instead.
_REGISTRY: dict[str, type[BaseScraper]] = {
    "demo": DemoScraper,
    "static": StaticScraper,
}


def get_scraper(site: str, site_cfg: SiteCfg | None = None) -> BaseScraper:
    cls = _REGISTRY.get(site, StaticScraper)
    return cls(site_cfg=site_cfg)
