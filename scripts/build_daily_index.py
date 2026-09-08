"""Compute the DAILY index from accumulated daily prices.

Uses the shared, unit-tested `chained_matched_index` from inflation/index.py
(chained, matched-sample — robust to composition changes and to the base day)
with the single sourced weights file config/weights.yaml.

Output: data/indice_quotidien.csv  (date, indice_quotidien, n_produits)

    python scripts/build_daily_index.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inflation.index import chained_matched_index  # noqa: E402

PRICES = Path("data/prix_actuels.csv")
OUT = Path("data/indice_quotidien.csv")
WEIGHTS = Path("config/weights.yaml")

# retail category -> CPI division (weights come from config/weights.yaml)
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


def main() -> None:
    if not PRICES.exists():
        print("Aucun relevé — lance d'abord scripts/collect_daily.py")
        return
    df = pd.read_csv(PRICES)
    if df.empty:
        print("Fichier de prix vide.")
        return

    weights = yaml.safe_load(WEIGHTS.read_text(encoding="utf-8"))["divisions"]
    prod_cat = df.drop_duplicates("product_id").set_index("product_id")["categorie"]
    category_of = {pid: DIVISION.get(c, "Autre") for pid, c in prod_cat.items()}

    wide = df.pivot_table(index="date", columns="product_id", values="prix",
                          aggfunc="median").sort_index()

    out = (chained_matched_index(wide, category_of, weights)
           .rename(columns={"period": "date", "value": "indice_quotidien"}))
    n = wide.notna().sum(axis=1).rename("n_produits")
    out = out.merge(n, left_on="date", right_index=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Indice quotidien (chaîné): {len(out)} jour(s), base 100 le {wide.index[0]} "
          f"-> {OUT}")
    print(out.tail(7).to_string(index=False))


if __name__ == "__main__":
    main()
