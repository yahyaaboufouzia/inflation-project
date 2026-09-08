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
HOUSING_OUT = Path("data/serie_logement.csv")
WEIGHTS = Path("config/weights.yaml")

_CFG = yaml.safe_load(WEIGHTS.read_text(encoding="utf-8"))
DIVISION = _CFG["division_of_category"]   # single source of truth (config/weights.yaml)


def compute_daily(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pure function (source -> outputs), so a test can reproduce the committed
    files exactly. Returns (headline index, housing series).

    Housing (Mubawab rent) is a very noisy listing proxy — one median that can
    swing on composition, not a real price change — so it is kept as a SEPARATE
    labelled series, out of the headline index (real CPIs survey rents
    quarterly, not daily).
    """
    weights = _CFG["divisions"]

    housing = (df[df["categorie"] == "logement"][["date", "prix"]]
               .rename(columns={"prix": "loyer_dh_m2"}).sort_values("date")
               .reset_index(drop=True))
    core = df[df["categorie"] != "logement"]

    prod_cat = core.drop_duplicates("product_id").set_index("product_id")["categorie"]
    category_of = {pid: DIVISION.get(c, "Autre") for pid, c in prod_cat.items()}
    wide = core.pivot_table(index="date", columns="product_id", values="prix",
                            aggfunc="median").sort_index()

    out = (chained_matched_index(wide, category_of, weights)
           .rename(columns={"period": "date", "value": "indice_quotidien"}))
    n = wide.notna().sum(axis=1).rename("n_produits")
    out = out.merge(n, left_on="date", right_index=True).reset_index(drop=True)
    return out, housing


def main() -> None:
    if not PRICES.exists():
        print("Aucun relevé — lance d'abord scripts/collect_daily.py")
        return
    df = pd.read_csv(PRICES)
    if df.empty:
        print("Fichier de prix vide.")
        return

    out, housing = compute_daily(df)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    if not housing.empty:
        housing.to_csv(HOUSING_OUT, index=False, encoding="utf-8")
    print(f"Indice quotidien (chaîné): {len(out)} jour(s) -> {OUT}")
    print(out.tail(7).to_string(index=False))


if __name__ == "__main__":
    main()
