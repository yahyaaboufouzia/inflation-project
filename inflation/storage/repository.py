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
