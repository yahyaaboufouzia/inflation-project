"""Generic scraper for static HTML pages (httpx + BeautifulSoup).

Works for any site whose price is present in the initial HTML. The CSS selector
comes from config (sites.yaml or a per-product override), so supporting a new
static site is usually a config change, not a code change. Sites that render
the price with JavaScript need a Playwright-based scraper instead.
"""
from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from ..cleaning import parse_price
from ..config import ProductCfg, SiteCfg
from .base import BaseScraper, PriceResult


class StaticScraper(BaseScraper):
    site = "static"

    def __init__(self, site_cfg: SiteCfg | None = None, timeout: float = 20.0):
        super().__init__(site_cfg)
        self._client = httpx.Client(
            headers={"User-Agent": self.site_cfg.user_agent},
            timeout=timeout,
            follow_redirects=True,
        )

    def fetch_price(self, product: ProductCfg) -> PriceResult:
        selector = product.selector or self.site_cfg.selector
        if not selector:
            raise ValueError(
                f"No CSS selector for product {product.id!r}; set one in "
                f"sites.yaml or on the product."
            )

        resp = self._client.get(product.url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        node = soup.select_one(selector)
        price = parse_price(node.get_text()) if node else None

        in_stock = True
        if self.site_cfg.in_stock:
            in_stock = soup.select_one(self.site_cfg.in_stock) is not None

        return PriceResult(
            product_id=product.id,
            price=price,
            in_stock=in_stock and price is not None,
            raw=(node.get_text(strip=True) if node else ""),
        )

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass
