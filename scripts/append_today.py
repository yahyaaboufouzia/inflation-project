"""Append today's REAL retail prices to the running dataset.

Scrapes the current Aswak Assalam prices for the tracked products, converts
each to MAD per kg (so they are comparable with the FAOSTAT base), and appends
one dated row per product to data/prix_actuels.csv. Idempotent per day.

Run by the daily collector (scripts/daily_collect.bat / Task Scheduler):

    python scripts/append_today.py
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inflation.config import load_basket  # noqa: E402
from inflation.scrapers.registry import get_scraper  # noqa: E402
from inflation.config import load_sites  # noqa: E402

OUT = Path("data/prix_actuels.csv")


def unit_to_kg(unit: str) -> float | None:
    """Convert a pack label to kilograms, or None if not weight-based."""
    u = unit.lower().replace(" ", "")
    m = re.fullmatch(r"(\d+)x(\d+)(g|kg)", u)  # e.g. 2x200g
    if m:
        n, q, s = int(m[1]), int(m[2]), m[3]
        return n * q / (1000 if s == "g" else 1)
    m = re.fullmatch(r"([\d.]+)(g|kg|l)", u)  # e.g. 250g, 1kg, 1l
    if m:
        q, s = float(m[1]), m[2]
        return q / 1000 if s == "g" else q  # treat 1L ~ 1kg
    return None


def main() -> None:
    basket = load_basket("config")
    sites = load_sites("config")
    today = date.today().isoformat()

    rows = []
    scrapers: dict[str, object] = {}
    for p in basket.products:
        if p.site not in scrapers:
            scrapers[p.site] = get_scraper(p.site, sites.get(p.site))
        try:
            res = scrapers[p.site].fetch_price(p)
        except Exception as exc:
            print(f"  ! {p.id}: {exc}")
            continue
        if res.price is None:
            continue
        kg = unit_to_kg(p.unit)
        rows.append({
            "date": today,
            "produit": p.name,
            "prix_dh": res.price,
            "unite": p.unit,
            "prix_mad_par_kg": round(res.price / kg, 2) if kg else None,
            "source_site": p.site,
            "source_url": p.url,
        })

    new = pd.DataFrame(rows)
    if OUT.exists():
        old = pd.read_csv(OUT)
        old = old[old["date"] != today]  # idempotent: replace today
        new = pd.concat([old, new], ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    new.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Appended {len(rows)} prices for {today}. Total rows: {len(new)}.")


if __name__ == "__main__":
    main()
