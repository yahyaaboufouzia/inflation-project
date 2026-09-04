"""Database schema.

Four tables mirror the four moving parts of the project:

    categories          spending buckets and their budget weight
    products            the basket (what we track, and where)
    price_observations  the raw time series — one row per product per scrape
    index_values        the computed daily index (a cache; always rebuildable)

`price_observations` is the append-only audit trail. Everything else is derived
from it, so the index can always be recomputed from scratch — that
reproducibility is the whole point of the project.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    weight: Mapped[float] = mapped_column(Float)  # budget share, categories sum to 1

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"))
    unit: Mapped[str] = mapped_column(String, default="")
    site: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped["Category"] = relationship(back_populates="products")
    observations: Mapped[list["PriceObservation"]] = relationship(
        back_populates="product"
    )


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String, default="MAD")
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    # provenance: where this exact value came from (the audit trail)
    source_site: Mapped[str] = mapped_column(String, default="")
    source_url: Mapped[str] = mapped_column(String, default="")

    product: Mapped["Product"] = relationship(back_populates="observations")


class IndexValue(Base):
    __tablename__ = "index_values"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    base_day: Mapped[date] = mapped_column(Date)
