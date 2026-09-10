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
import sys
from pathlib import Path

import httpx
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from inflation.index import index_from_relatives  # noqa: E402

OUT = ROOT / "data" / "validation_usa.csv"
METRICS_OUT = ROOT / "data" / "validation_metrics.csv"
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
FOOD_WEIGHTS = yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "config" / "weights.yaml")
    .read_text(encoding="utf-8"))["food_subcategories"]


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
    rel.index.name = "period"
    long = (rel.reset_index()
            .melt(id_vars="period", var_name="label", value_name="relative")
            .dropna(subset=["relative"]))
    long["category"] = long["label"].map(cats)
    out = index_from_relatives(long[["period", "category", "relative"]], FOOD_WEIGHTS)
    return out.rename(columns={"period": "annee", "value": "indice_nous_usa"})


def main() -> None:
    ours = our_us_index()
    cpi = fred("CPIUFDSL")  # official US food CPI
    cpi = (cpi / cpi.loc[BASE_YEAR] * 100).reset_index()
    cpi.columns = ["annee", "cpi_food_usa"]

    m = ours.merge(cpi, on="annee", how="inner").sort_values("annee").reset_index(drop=True)
    m.to_csv(OUT, index=False, encoding="utf-8")

    # --- honest validation metrics ------------------------------------------
    # NOTE: correlating index LEVELS is spurious (Granger-Newbold): two rising
    # non-stationary series always correlate ~0.99 — even a bogus exp(0.03 t)
    # trend beats us. The real test is on year-over-year RATES (stationary).
    m = m.sort_values("annee")
    yoy_n = m["indice_nous_usa"].pct_change() * 100
    yoy_o = m["cpi_food_usa"].pct_change() * 100
    ok = yoy_n.notna() & yoy_o.notna()
    yoy_corr = yoy_n[ok].corr(yoy_o[ok])
    mae = (yoy_n[ok] - yoy_o[ok]).abs().mean()
    cum_n = (m["indice_nous_usa"].iloc[-1] / m["indice_nous_usa"].iloc[0] - 1) * 100
    cum_o = (m["cpi_food_usa"].iloc[-1] / m["cpi_food_usa"].iloc[0] - 1) * 100

    print(f"\nWrote {OUT}: {len(m)} years ({m['annee'].min()}-{m['annee'].max()})")
    print("Honest metrics (do NOT report the level correlation):")
    print(f"  YoY-rate correlation : {yoy_corr:.3f}")
    print(f"  MAE on annual rates  : {mae:.2f} pts")
    print(f"  Cumulative inflation : ours {cum_n:.0f}% vs official {cum_o:.0f}%")

    pd.DataFrame([{"yoy_corr": round(yoy_corr, 3), "mae_pts": round(mae, 2),
                   "cum_ours_pct": round(cum_n), "cum_official_pct": round(cum_o),
                   "annee_min": int(m["annee"].min()), "annee_max": int(m["annee"].max()),
                   "n_produits": len(US_BASKET)}]).to_csv(
        METRICS_OUT, index=False, encoding="utf-8")


if __name__ == "__main__":
    main()
