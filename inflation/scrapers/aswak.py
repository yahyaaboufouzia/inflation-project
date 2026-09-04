"""Real scraper for Aswak Assalam (aswakassalam.com).

Aswak Assalam is a Moroccan hypermarket chain whose online store runs on
WooCommerce: prices sit directly in the HTML (no JavaScript needed), so a plain
httpx + BeautifulSoup fetch works. Each product page carries a canonical URL,
which we keep as the provenance of every price.

Sale handling: a discounted product shows two amounts inside `.price`
(<del> old, <ins> new). The *current* price is the last amount, which is what
we record.
"""
from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from ..cleaning import parse_price
from ..config import ProductCfg, SiteCfg
from .base import BaseScraper, PriceResult


class AswakAssalamScraper(BaseScraper):
    site = "aswak"

    def __init__(self, site_cfg: SiteCfg | None = None, timeout: float = 25.0):
        super().__init__(site_cfg)
        self._client = httpx.Client(
            headers={
                "User-Agent": self.site_cfg.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "fr-FR,fr;q=0.9,ar;q=0.8",
            },
            timeout=timeout,
            follow_redirects=True,
        )

    def fetch_price(self, product: ProductCfg) -> PriceResult:
        resp = self._client.get(product.url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # the main product price lives in the summary block, not in related items
        block = soup.select_one(".summary .price") or soup.select_one("p.price")
        amounts = block.select(".woocommerce-Price-amount") if block else []
        price = parse_price(amounts[-1].get_text(" ", strip=True)) if amounts else None

        out_of_stock = soup.select_one(".stock.out-of-stock") is not None

        return PriceResult(
            product_id=product.id,
            price=price,
            in_stock=(price is not None) and not out_of_stock,
            scraped_at=None,  # defaults to now
            raw=(amounts[-1].get_text(strip=True) if amounts else ""),
        )

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass
