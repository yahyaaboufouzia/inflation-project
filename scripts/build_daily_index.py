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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from inflation.index import chained_matched_index, family_keys  # noqa: E402

PRICES = ROOT / "data" / "prix_actuels.csv"
OUT = ROOT / "data" / "indice_quotidien.csv"
HOUSING_OUT = ROOT / "data" / "serie_logement.csv"
WEIGHTS = ROOT / "config" / "weights.yaml"

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

    # tolerate older price files that predate the promo columns
    if "prix_reference" not in df.columns:
        df = df.assign(prix_reference=df["prix"])
    else:
        df["prix_reference"] = df["prix_reference"].fillna(df["prix"])
    if "en_promo" not in df.columns:
        df = df.assign(en_promo=False)

    housing = (df[df["categorie"] == "logement"][["date", "prix"]]
               .rename(columns={"prix": "loyer_dh_m2"}).sort_values("date")
               .reset_index(drop=True))
    core = df[df["categorie"] != "logement"]

    # fail loudly if a collected category has no division mapping — otherwise it
    # would silently get weight 0 and never enter the index
    unmapped = set(core["categorie"]) - set(DIVISION)
    if unmapped:
        raise ValueError(f"catégories non mappées dans weights.yaml : {sorted(unmapped)}")

    prod_cat = core.drop_duplicates("product_id").set_index("product_id")["categorie"]
    category_of = {pid: DIVISION.get(c, "Autre") for pid, c in prod_cat.items()}
    family_of = family_keys(prod_cat.index)   # collapse range variants

    def series(value_col: str) -> pd.DataFrame:
        wide = core.pivot_table(index="date", columns="product_id", values=value_col,
                                aggfunc="median").sort_index()
        return chained_matched_index(wide, category_of, weights, family_of)

    disp = series("prix").rename(columns={"period": "date", "value": "indice_quotidien"})
    ref = series("prix_reference").rename(columns={"period": "date", "value": "indice_reference"})
    out = disp.merge(ref, on="date")

    # per-day: products matched, and share of them on promotion
    wide_disp = core.pivot_table(index="date", columns="product_id", values="prix",
                                 aggfunc="median").sort_index()
    out = out.merge(wide_disp.notna().sum(axis=1).rename("n_produits"),
                    left_on="date", right_index=True)
    promo = (core.assign(en_promo=core["en_promo"].astype(bool))
             .groupby("date")["en_promo"].mean().mul(100).round(1).rename("pct_en_promo"))
    out = out.merge(promo, left_on="date", right_index=True, how="left").reset_index(drop=True)
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
