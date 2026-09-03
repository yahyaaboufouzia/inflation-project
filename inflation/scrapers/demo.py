"""A synthetic scraper — no network, fully deterministic.

Its job is to make the project run the moment it is cloned: it invents a stable
base price per product and applies a slow upward drift plus a small daily
wiggle. That yields a realistic-looking index without hitting any real site,
so `seed_demo.py` can build months of history offline and the dashboard has
something to show immediately.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from ..config import ProductCfg, SiteCfg
from .base import BaseScraper, PriceResult


def _hash(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest(), 16)


def _base_price(product_id: str) -> float:
    """A stable pseudo-random base price in roughly [20, 420] MAD."""
    return 20.0 + (_hash(product_id) % 4000) / 10.0


class DemoScraper(BaseScraper):
    site = "demo"

    def __init__(
        self,
        site_cfg: SiteCfg | None = None,
        day: datetime | None = None,
        annual_drift: float = 0.06,
    ):
        super().__init__(site_cfg)
        self.day = day or datetime.now()
        self.annual_drift = annual_drift  # ~6% "official-ish" trend per year

    def fetch_price(self, product: ProductCfg) -> PriceResult:
        base = _base_price(product.id)

        # deterministic daily wiggle in +/- 1%, unique per product and day
        seed = _hash(f"{product.id}:{self.day:%Y-%m-%d}")
        wiggle = ((seed % 1000) / 1000.0 - 0.5) * 0.02

        # smooth upward drift proportional to elapsed days in the year
        t = (self.day.timetuple().tm_yday - 1) / 365.0
        price = base * (1.0 + self.annual_drift * t + wiggle)

        return PriceResult(
            product_id=product.id,
            price=round(price, 2),
            in_stock=True,
            scraped_at=self.day,
            raw="demo",
        )
