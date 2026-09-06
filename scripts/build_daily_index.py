"""Compute the DAILY inflation index from the accumulated daily prices.

Method (matched-model, base = first collection day = 100):
  - price relative per product: r(i,t) = prix(i,t) / prix(i, base)
  - Jevons (geometric mean) within each category
  - equal average across categories (so a category with many products does not
    dominate)
Only products present on the base day anchor the index; the series grows one
point per collection day.

Output: data/indice_quotidien.csv  (date, indice_quotidien, n_produits)

    python scripts/build_daily_index.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PRICES = Path("data/prix_actuels.csv")
OUT = Path("data/indice_quotidien.csv")


def main() -> None:
    if not PRICES.exists():
        print("Aucun relevé — lance d'abord scripts/collect_daily.py")
        return
    df = pd.read_csv(PRICES)
    if df.empty:
        print("Fichier de prix vide.")
        return

    cats = df.drop_duplicates("product_id").set_index("product_id")["categorie"]
    wide = df.pivot_table(index="date", columns="product_id", values="prix", aggfunc="median")
    wide = wide.sort_index()

    base_date = wide.index[0]
    p0 = wide.loc[base_date]
    valid = p0.dropna().index
    rel = wide[valid].divide(p0[valid])

    rows = []
    for day, row in rel.iterrows():
        r = row.dropna()
        if r.empty:
            continue
        cat_vals: dict[str, list[float]] = {}
        for pid, v in r.items():
            cat_vals.setdefault(cats.get(pid, "?"), []).append(v)
        cat_idx = [float(np.exp(np.mean(np.log(vs)))) for vs in cat_vals.values()]  # Jevons
        rows.append({"date": day,
                     "indice_quotidien": round(100 * float(np.mean(cat_idx)), 2),
                     "n_produits": int(len(r))})

    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Indice quotidien: {len(out)} jour(s), base 100 le {base_date}, "
          f"{len(valid)} produits suivis -> {OUT}")
    if not out.empty:
        print(out.tail(7).to_string(index=False))


if __name__ == "__main__":
    main()
