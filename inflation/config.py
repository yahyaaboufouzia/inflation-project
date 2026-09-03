"""Declarative configuration: the basket, category weights and site settings.

The basket and weights live in YAML so that changing *what* we measure never
requires touching *how* we measure it. Everything is validated on load, so a
typo (weights that do not sum to 1, a product pointing at an unknown category)
fails loudly instead of silently corrupting the index.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

CONFIG_DIR = Path("config")


class CategoryCfg(BaseModel):
    id: str
    name: str
    weight: float = Field(gt=0, le=1)


class ProductCfg(BaseModel):
    id: str
    name: str
    category: str
    site: str
    url: str
    unit: str = ""
    active: bool = True
    selector: str | None = None  # optional per-product CSS override
    base_price: float | None = None  # realistic starting price (MAD) for the demo


class SiteCfg(BaseModel):
    type: str = "static"
    selector: str | None = None
    in_stock: str | None = None
    delay: float = 2.0
    user_agent: str = "Mozilla/5.0 (compatible; MoroccoInflationTracker/0.1; research)"


class Basket(BaseModel):
    categories: list[CategoryCfg]
    products: list[ProductCfg]

    def validate_weights(self) -> None:
        total = sum(c.weight for c in self.categories)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Category weights must sum to 1.0 (got {total:.4f})")

    def validate_refs(self) -> None:
        known = {c.id for c in self.categories}
        missing = {p.category for p in self.products} - known
        if missing:
            raise ValueError(f"Products reference unknown categories: {sorted(missing)}")

    @property
    def weight_by_category(self) -> dict[str, float]:
        return {c.id: c.weight for c in self.categories}


def load_basket(config_dir: Path | str = CONFIG_DIR) -> Basket:
    config_dir = Path(config_dir)
    weights = yaml.safe_load((config_dir / "weights.yaml").read_text(encoding="utf-8"))
    basket = yaml.safe_load((config_dir / "basket.yaml").read_text(encoding="utf-8"))
    b = Basket(
        categories=[CategoryCfg(**c) for c in weights["categories"]],
        products=[ProductCfg(**p) for p in basket["products"]],
    )
    b.validate_weights()
    b.validate_refs()
    return b


def load_sites(config_dir: Path | str = CONFIG_DIR) -> dict[str, SiteCfg]:
    config_dir = Path(config_dir)
    path = config_dir / "sites.yaml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {name: SiteCfg(**cfg) for name, cfg in (raw.get("sites") or {}).items()}
