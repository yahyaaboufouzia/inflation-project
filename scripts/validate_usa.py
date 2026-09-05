"""Validate the METHOD against a ground-truth benchmark: the USA.

Where real retail prices exist (they do for the US, via BLS/FRED average
prices), our exact index method (Jevons within category, Laspeyres across)
should reproduce the official CPI. If it does, the method is proven — and the
Morocco gap is a *data* problem (we only have producer prices there), not a
method problem.

Fetches US retail prices per product (FRED "Average Price" APU series, no key),
builds our index, and compares it to the official US food CPI (FRED CPIUFDSL).

Output: data/validation_usa.csv  (year, our US index, official US food CPI)

    python scripts/validate_usa.py
"""
from __future__ import annotations

import io
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

OUT = Path("data/validation_usa.csv")
BASE_YEAR = 2000

# Retail average-price series (FRED APU codes) grouped like the Morocco basket.
US_BASKET = {
    "Pain (blanc, /lb)":      ("APU0000702111", "Céréales"),
    "Farine (/lb)":           ("APU0000701111", "Céréales"),
    "Riz (blanc, /lb)":       ("APU0000701312", "Céréales"),
    "Poulet (entier, /lb)":   ("APU0000706111", "Viandes"),
    "Boeuf haché (/lb)":      ("APU0000703112", "Viandes"),
    "Oeufs (grade A, /doz)":  ("APU0000708111", "Produits animaux"),
    "Lait (entier, /gal)":    ("APU0000709112", "Produits animaux"),
    "Bananes (/lb)":          ("APU0000711211", "Fruits"),
    "Oranges (navel, /lb)":   ("APU0000711311", "Fruits"),
    "Tomates (/lb)":          ("APU0000712311", "Légumes"),
    "Pommes de terre (/lb)":  ("APU0000712112", "Légumes"),
    "Café (moulu, /lb)":      ("APU0000717311", "Boissons"),
    "Sucre (/lb)":            ("APU0000715211", "Sucre"),
}
CATEGORY_WEIGHTS = {
    "Céréales": 0.30, "Viandes": 0.25, "Produits animaux": 0.18,
    "Fruits": 0.10, "Légumes": 0.10, "Boissons": 0.04, "Sucre": 0.03,
}


def fred(series_id: str) -> pd.Series | None:
    r = httpx.get("https://fred.stlouisfed.org/graph/fredgraph.csv",
                  params={"id": series_id}, headers={"User-Agent": "Mozilla/5.0"},
                  timeout=60, follow_redirects=True)
    if r.status_code != 200 or "<html" in r.text[:100].lower():
        return None
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "value"]
    df = df[df["value"] != "."]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["year"] = pd.to_datetime(df["date"]).dt.year
    return df.groupby("year")["value"].mean()  # annual average


def our_us_index() -> pd.DataFrame:
    prices, cats = {}, {}
    for label, (sid, cat) in US_BASKET.items():
        s = fred(sid)
        if s is None or BASE_YEAR not in s.index:
            print(f"  - skip {label} ({sid})")
            continue
        prices[label] = s / s.loc[BASE_YEAR]  # price relative, base 2000
        cats[label] = cat
        print(f"  + {label}: {len(s)} years")

    rel = pd.DataFrame(prices)
    rows = []
    for year, row in rel.iterrows():
        cat_rel, cat_w = {}, {}
        for label, r in row.dropna().items():
            c = cats[label]
            cat_rel.setdefault(c, []).append(r)
            cat_w[c] = CATEGORY_WEIGHTS.get(c, 0.0)
        vals, ws = [], []
        for c, rs in cat_rel.items():
            vals.append(float(np.exp(np.mean(np.log(rs)))))  # Jevons
            ws.append(cat_w[c])
        if sum(ws) == 0:
            continue
        rows.append((int(year), round(100 * float(np.average(vals, weights=ws)), 2)))
    return pd.DataFrame(rows, columns=["annee", "indice_nous_usa"])


def main() -> None:
    ours = our_us_index()
    cpi = fred("CPIUFDSL")  # official US food CPI
    cpi = (cpi / cpi.loc[BASE_YEAR] * 100).reset_index()
    cpi.columns = ["annee", "cpi_food_usa"]

    m = ours.merge(cpi, on="annee", how="inner").sort_values("annee").reset_index(drop=True)
    m.to_csv(OUT, index=False, encoding="utf-8")

    corr = m["indice_nous_usa"].corr(m["cpi_food_usa"])
    print(f"\nWrote {OUT}: {len(m)} years ({m['annee'].min()}-{m['annee'].max()})")
    print(f"Corrélation notre indice US vs CPI alimentaire officiel US : {corr:.4f}")
    print(m[m["annee"] >= 2018].to_string(index=False))


if __name__ == "__main__":
    main()
