"""Build OUR inflation index and compare it fairly to the official series.

Three methodological corrections make the comparison apples-to-apples:
  1. Coverage — we compare to the official FOOD CPI (not the all-items index),
     since our basket is food only.
  2. Producer -> retail — producer (farm-gate) prices are far more volatile than
     shelf prices, so we also publish a SMOOTHED version (3-year moving average)
     that approximates the stickiness of retail prices.
  3. Weighting — category weights follow a household food-consumption structure.

Sources (both from FAOSTAT, base 2015=100, rebased here to 2010=100):
  - Consumer Prices, Food Indices     -> official food inflation
  - Consumer Prices, General Indices  -> official all-items inflation (context)

Outputs:
  data/official/cpi_maroc_faostat.csv   official food + general CPI (annual)
  data/indice_inflation.csv             our index (+ smoothed) vs official

    python scripts/build_inflation_index.py
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import httpx
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from inflation.index import index_from_relatives  # noqa: E402

FAOSTAT_PRICES = ROOT / "data" / "prix_maroc_faostat.csv"
CP_BULK = "https://bulks-faostat.fao.org/production/ConsumerPriceIndices_E_All_Data_(Normalized).zip"
CPI_OUT = ROOT / "data" / "official" / "cpi_maroc_faostat.csv"
INDEX_OUT = ROOT / "data" / "indice_inflation.csv"
WEIGHTS = ROOT / "config" / "weights.yaml"
BASE_YEAR = 2010

FOOD_WEIGHTS = yaml.safe_load(WEIGHTS.read_text(encoding="utf-8"))["food_subcategories"]


def our_index(prices: pd.DataFrame) -> pd.DataFrame:
    p = prices[["produit", "categorie", "annee", "prix_mad_par_kg"]].dropna()
    base = (p[p["annee"] == BASE_YEAR][["produit", "prix_mad_par_kg"]]
            .rename(columns={"prix_mad_par_kg": "p0"}))
    p = p.merge(base, on="produit", how="inner")
    p["relative"] = p["prix_mad_par_kg"] / p["p0"]
    long = p.rename(columns={"annee": "period", "categorie": "category"})
    out = index_from_relatives(long[["period", "category", "relative"]], FOOD_WEIGHTS)
    return out.rename(columns={"period": "annee", "value": "indice_nous"})


def _rebase(s: pd.Series, years: pd.Series) -> pd.Series:
    ref = s[years == BASE_YEAR]
    if ref.empty:
        return s / s.iloc[0] * 100
    return s / ref.iloc[0] * 100


def official_cpi() -> pd.DataFrame:
    r = httpx.get(CP_BULK, headers={"User-Agent": "Mozilla/5.0"}, timeout=300,
                  follow_redirects=True)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    csv = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    df = pd.read_csv(z.open(csv), encoding="latin-1", low_memory=False)
    df = df[df["Area"] == "Morocco"]

    def annual(item: str) -> pd.DataFrame:
        d = df[df["Item"] == item]
        a = d.groupby("Year")["Value"].mean().reset_index()  # mean of the 12 months
        return a.rename(columns={"Year": "annee", "Value": "v"})

    food = annual("Consumer Prices, Food Indices (2015 = 100)")
    gen = annual("Consumer Prices, General Indices (2015 = 100)")
    out = food.merge(gen, on="annee", suffixes=("_food", "_gen"))
    out["cpi_food_officiel"] = _rebase(out["v_food"], out["annee"]).round(2)
    out["cpi_general_officiel"] = _rebase(out["v_gen"], out["annee"]).round(2)
    res = out[["annee", "cpi_food_officiel", "cpi_general_officiel"]]

    CPI_OUT.parent.mkdir(parents=True, exist_ok=True)
    save = res.copy()
    save["source"] = "FAOSTAT - Consumer Price Indices (Maroc), base 2015=100 rebasée 2010=100"
    save["source_url"] = "https://www.fao.org/faostat/fr/#data/CP"
    save.to_csv(CPI_OUT, index=False, encoding="utf-8")
    return res


def main() -> None:
    ours = our_index(pd.read_csv(FAOSTAT_PRICES))
    # Fix 2 — smoothed index approximating sticky retail prices
    ours["indice_nous_lisse"] = (ours["indice_nous"]
                                 .rolling(3, center=True, min_periods=1).mean().round(2))
    official = official_cpi()  # Fix 1 — official FOOD CPI (+ general for context)

    m = ours.merge(official, on="annee", how="outer").sort_values("annee").reset_index(drop=True)
    m["inflation_nous_%"] = (m["indice_nous"].pct_change() * 100).round(2)
    m["inflation_food_off_%"] = (m["cpi_food_officiel"].pct_change() * 100).round(2)
    m.to_csv(INDEX_OUT, index=False, encoding="utf-8")

    print(f"Wrote {INDEX_OUT}: {len(m)} years")
    print(m[m["annee"] >= 2019].to_string(index=False))


if __name__ == "__main__":
    main()
