"""The scraper interface.

Adding a new site means writing one class that implements `fetch_price`.
Everything downstream (pipeline, storage, index) is written against this
interface and never needs to change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from ..config import ProductCfg, SiteCfg


@dataclass
class PriceResult:
    product_id: str
    price: float | None
    in_stock: bool = True
    currency: str = "MAD"
    scraped_at: datetime = field(default_factory=datetime.now)
    raw: str = ""  # snapshot of what was scraped, for the audit trail


class BaseScraper(ABC):
    """Base class for site scrapers."""

    site: str = "base"

    def __init__(self, site_cfg: SiteCfg | None = None):
        self.site_cfg = site_cfg or SiteCfg()

    @abstractmethod
    def fetch_price(self, product: ProductCfg) -> PriceResult:
        """Return the current price for a single product."""
        raise NotImplementedError
