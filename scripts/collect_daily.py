"""Collect today's prices for the whole catalog and append them (dated).

Re-scrapes the Aswak category pages (efficient: one request lists many
products) and appends one row per product for today. Idempotent: re-running the
same day replaces today's rows. This is what makes the index DAILY — a new
dated observation for every product, every day.

Output (appended): data/prix_actuels.csv
    date, product_id, produit, categorie, prix, source_url

    python scripts/collect_daily.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))         # scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root

from scrape_aswak_catalog import scrape_category  # noqa: E402

CATALOG = Path("data/aswak_catalog.csv")
OUT = Path("data/prix_actuels.csv")


def main() -> None:
    if not CATALOG.exists():
        print("Catalogue absent — lance d'abord scripts/scrape_aswak_catalog.py")
        return
    cats = sorted(pd.read_csv(CATALOG)["categorie"].unique())
    today = date.today().isoformat()

    rows = []
    for slug in cats:
        for p in scrape_category(slug):
            if p["prix"] is None:
                continue
            rows.append({
                "date": today,
                "product_id": p["product_id"],
                "produit": p["produit"],
                "categorie": p["categorie"],
                "prix": p["prix"],
                "source_url": p["url"],
            })
        print(f"  {slug:28} cumulé {len(rows)} relevés", flush=True)

    new = pd.DataFrame(rows).drop_duplicates("product_id")
    if OUT.exists():
        old = pd.read_csv(OUT)
        old = old[old["date"] != today]  # idempotent
        new = pd.concat([old, new], ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    new.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Relevé {today}: {len(rows)} produits. Total historique: {len(new)} lignes.")


if __name__ == "__main__":
    main()
