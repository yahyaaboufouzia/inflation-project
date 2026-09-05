"""Build OUR inflation index from the FAOSTAT price base and compare it to the
official Morocco CPI (World Bank).

- Our index: a weighted basket of 21 Moroccan staples (data/prix_maroc_faostat.csv).
  Jevons (geometric mean) within each food category, Laspeyres across categories
  using household-style weights. Base 2010 = 100, to match the official series.
- Official: real Morocco CPI from the World Bank (indicator FP.CPI.TOTL,
  base 2010 = 100), fetched live and cached.

Outputs:
  data/official/cpi_maroc_worldbank.csv   the official CPI (source of truth)
  data/indice_inflation.csv               our index vs official, per year

    python scripts/build_inflation_index.py
"""
from __future__ import annotations

from pathlib import Path

import httpx
import numpy as np
import pandas as pd

FAOSTAT = Path("data/prix_maroc_faostat.csv")
CPI_OUT = Path("data/official/cpi_maroc_worldbank.csv")
INDEX_OUT = Path("data/indice_inflation.csv")
BASE_YEAR = 2010

# Household-style budget weights per FAOSTAT food category (sum to 1).
CATEGORY_WEIGHTS = {
    "Céréales": 0.28,          # bread, flour, couscous — the Moroccan staple
    "Viandes": 0.22,
    "Produits animaux": 0.14,  # milk, eggs
    "Légumes": 0.16,
    "Fruits": 0.12,
    "Légumineuses": 0.08,
}


def fetch_official_cpi() -> pd.DataFrame:
    r = httpx.get(
        "https://api.worldbank.org/v2/country/MAR/indicator/FP.CPI.TOTL",
        params={"format": "json", "per_page": "100", "date": "2000:2025"},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=60,
    )
    data = r.json()[1]
    rows = [(int(d["date"]), d["value"]) for d in data if d["value"] is not None]
    df = pd.DataFrame(sorted(rows), columns=["annee", "cpi_officiel"])
    df["source"] = "Banque mondiale - FP.CPI.TOTL (base 2010=100)"
    df["source_url"] = "https://data.worldbank.org/indicator/FP.CPI.TOTL?locations=MA"
    CPI_OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CPI_OUT, index=False, encoding="utf-8")
    return df


def our_index(prices: pd.DataFrame) -> pd.DataFrame:
    """Annual Laspeyres/Jevons index, base BASE_YEAR = 100."""
    p = prices[["produit", "categorie", "annee", "prix_mad_par_kg"]].dropna()
    base = (p[p["annee"] == BASE_YEAR][["produit", "prix_mad_par_kg"]]
            .rename(columns={"prix_mad_par_kg": "p0"}))
    p = p.merge(base, on="produit", how="inner")
    p["rel"] = p["prix_mad_par_kg"] / p["p0"]

    out = []
    for year, g in p.groupby("annee"):
        cat_rel, cat_w = {}, {}
        for cat, gc in g.groupby("categorie"):
            cat_rel[cat] = float(np.exp(np.log(gc["rel"]).mean()))  # Jevons
            cat_w[cat] = CATEGORY_WEIGHTS.get(cat, 0.0)
        w = np.array([cat_w[c] for c in cat_rel])
        v = np.array([cat_rel[c] for c in cat_rel])
        if w.sum() == 0:
            continue
        out.append((int(year), round(100.0 * float(np.average(v, weights=w)), 2)))
    return pd.DataFrame(out, columns=["annee", "indice_nous"])


def main() -> None:
    prices = pd.read_csv(FAOSTAT)
    ours = our_index(prices)
    official = fetch_official_cpi().rename(columns={"cpi_officiel": "indice_officiel"})

    merged = ours.merge(official[["annee", "indice_officiel"]], on="annee", how="outer")
    merged = merged.sort_values("annee").reset_index(drop=True)
    # year-over-year inflation rates (%)
    merged["inflation_nous_%"] = (merged["indice_nous"].pct_change() * 100).round(2)
    merged["inflation_officiel_%"] = (merged["indice_officiel"].pct_change() * 100).round(2)
    merged.to_csv(INDEX_OUT, index=False, encoding="utf-8")

    print(f"Wrote {INDEX_OUT}: {len(merged)} years")
    tail = merged[merged["annee"] >= 2018]
    print(tail.to_string(index=False))


if __name__ == "__main__":
    main()
