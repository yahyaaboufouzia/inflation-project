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

# Group the retail categories into CPI-style divisions and weight them so that
# housing carries its real (heavy) share instead of counting as one food category.
DIVISION = {
    "patisserie": "Alimentation", "boulangerie": "Alimentation",
    "fruits-legumes": "Alimentation", "boucherie-volaille": "Alimentation",
    "charcuterie-traiteur": "Alimentation", "cremerie": "Alimentation",
    "epicerie": "Alimentation", "biscuiterie-confiserie": "Alimentation",
    "boissons": "Alimentation",
    "beaute-hygiene": "Hygiène & entretien", "entretien": "Hygiène & entretien",
    "logement": "Logement", "carburant": "Transport",
    "maison-cuisine": "Équipement", "petit-electromenager": "Équipement",
    "gros-electromenager": "Équipement", "multimedia": "Équipement",
}
DIVISION_WEIGHTS = {
    "Alimentation": 0.45, "Logement": 0.22, "Transport": 0.13,
    "Hygiène & entretien": 0.08, "Équipement": 0.12,
}


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
        # Jevons within each division, then Laspeyres across divisions
        div_vals: dict[str, list[float]] = {}
        for pid, v in r.items():
            div = DIVISION.get(cats.get(pid, ""), "Autre")
            div_vals.setdefault(div, []).append(v)
        div_idx, weights = [], []
        for div, vs in div_vals.items():
            div_idx.append(float(np.exp(np.mean(np.log(vs)))))
            weights.append(DIVISION_WEIGHTS.get(div, 0.02))
        value = 100 * float(np.average(div_idx, weights=weights))
        rows.append({"date": day, "indice_quotidien": round(value, 2),
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
