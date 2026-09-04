"""Thin data-access layer over SQLite.

Deliberately function-based rather than a heavy ORM abstraction: read prices as
a pandas DataFrame (the shape the index math wants), write observations and the
computed index back. Nothing here knows about scraping or the index formula.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy import create_engine, delete
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ..config import Basket
from .models import Base, Category, IndexValue, PriceObservation, Product

DEFAULT_DB = Path("data/prices.db")


def get_engine(db_path: Path | str = DEFAULT_DB) -> Engine:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def sync_catalog(engine: Engine, basket: Basket) -> None:
    """Upsert categories and products from the parsed config into the DB."""
    with Session(engine) as s:
        for c in basket.categories:
            obj = s.get(Category, c.id)
            if obj is None:
                s.add(Category(id=c.id, name=c.name, weight=c.weight))
            else:
                obj.name, obj.weight = c.name, c.weight
        for p in basket.products:
            obj = s.get(Product, p.id)
            if obj is None:
                s.add(
                    Product(
                        id=p.id, name=p.name, category_id=p.category,
                        unit=p.unit, site=p.site, url=p.url, active=p.active,
                    )
                )
            else:
                obj.name, obj.category_id, obj.unit = p.name, p.category, p.unit
                obj.site, obj.url, obj.active = p.site, p.url, p.active
        s.commit()


def add_observations(engine: Engine, rows: Iterable[dict]) -> int:
    rows = list(rows)
    with Session(engine) as s:
        for r in rows:
            s.add(
                PriceObservation(
                    product_id=r["product_id"],
                    price=r["price"],
                    currency=r.get("currency", "MAD"),
                    in_stock=r.get("in_stock", True),
                    scraped_at=r.get("scraped_at") or datetime.now(),
                    source_site=r.get("source_site", ""),
                    source_url=r.get("source_url", ""),
                )
            )
        s.commit()
    return len(rows)


def observations_df(engine: Engine) -> pd.DataFrame:
    """In-stock observations joined with their category and weight.

    Columns: product_id, product_name, price, scraped_at, category_id,
    category_name, category_weight.
    """
    sql = """
        SELECT o.product_id,
               p.name           AS product_name,
               o.price,
               o.scraped_at,
               p.category_id,
               c.name           AS category_name,
               c.weight         AS category_weight
        FROM price_observations o
        JOIN products p   ON p.id = o.product_id
        JOIN categories c ON c.id = p.category_id
        WHERE o.in_stock = 1
    """
    return pd.read_sql_query(sql, engine, parse_dates=["scraped_at"])


def save_index(engine: Engine, index_df: pd.DataFrame) -> None:
    """Replace the cached index with a freshly computed one."""
    with Session(engine) as s:
        s.execute(delete(IndexValue))
        for _, r in index_df.iterrows():
            s.add(
                IndexValue(day=r["day"], value=float(r["value"]), base_day=r["base_day"])
            )
        s.commit()


def index_df(engine: Engine) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT day, value, base_day FROM index_values ORDER BY day",
        engine,
        parse_dates=["day", "base_day"],
    )


# --- CSV persistence ---------------------------------------------------------
# The raw observations are the versioned source of truth: we commit them as a
# text CSV so the price history lives in Git (public, diffable, reproducible).
# The SQLite file is only a local cache, always rebuildable from this CSV.

def export_observations_csv(engine: Engine, path: Path | str) -> int:
    """Write every raw observation to a CSV. Returns the row count."""
    df = pd.read_sql_query(
        "SELECT product_id, price, currency, in_stock, scraped_at, "
        "source_site, source_url "
        "FROM price_observations ORDER BY scraped_at, product_id",
        engine,
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return len(df)


def import_observations_csv(engine: Engine, path: Path | str) -> int:
    """Load observations from a CSV back into the DB. Returns rows inserted."""
    path = Path(path)
    if not path.exists():
        return 0
    df = pd.read_csv(path, parse_dates=["scraped_at"])
    rows = [
        {
            "product_id": r["product_id"],
            "price": float(r["price"]),
            "currency": r.get("currency", "MAD"),
            "in_stock": bool(r["in_stock"]),
            "scraped_at": r["scraped_at"].to_pydatetime(),
            "source_site": r.get("source_site", "") if pd.notna(r.get("source_site")) else "",
            "source_url": r.get("source_url", "") if pd.notna(r.get("source_url")) else "",
        }
        for _, r in df.iterrows()
    ]
    return add_observations(engine, rows)
