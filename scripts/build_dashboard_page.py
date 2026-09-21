"""Regenerate the public dashboard page (docs/index.html) from the current CSVs.

The page's charts are driven by a single `const DATA = {...};` line. This script
rebuilds that object from the committed data and swaps the line in place, so the
public GitHub Pages site shows the latest daily index after each collection
without touching the hand-made design.

    python scripts/build_dashboard_page.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PAGE = ROOT / "docs" / "index.html"


def _read(name: str) -> pd.DataFrame:
    p = DATA_DIR / name
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def _col(df: pd.DataFrame, c: str) -> list:
    if c not in df:
        return []
    return [None if pd.isna(x) else round(float(x), 2) for x in df[c]]


def build_data() -> dict:
    out: dict = {}

    di = _read("indice_quotidien.csv")
    if not di.empty:
        out["daily"] = {"dates": di["date"].astype(str).tolist(),
                        "index": _col(di, "indice_quotidien"),
                        "n": [int(x) for x in di["n_produits"]]}

    lr = _read("indice_inflation.csv")
    if not lr.empty:
        out["longrun"] = {"years": [int(y) for y in lr["annee"]],
                          "ours": _col(lr, "indice_nous"),
                          "ours_smooth": _col(lr, "indice_nous_lisse"),
                          "food_off": _col(lr, "cpi_food_officiel"),
                          "gen_off": _col(lr, "cpi_general_officiel")}

    v = _read("validation_usa.csv")
    if not v.empty:
        out["validation"] = {"years": [int(y) for y in v["annee"]],
                             "ours": _col(v, "indice_nous_usa"),
                             "cpi": _col(v, "cpi_food_usa")}

    m = _read("validation_metrics.csv")
    if not m.empty:
        r = m.iloc[0]
        out["metrics"] = {"yoy_corr": round(float(r["yoy_corr"]), 3),
                          "mae_pts": round(float(r["mae_pts"]), 1),
                          "cum_ours_pct": round(float(r["cum_ours_pct"]), 0),
                          "cum_official_pct": round(float(r["cum_official_pct"]), 0)}

    fa = _read("prix_maroc_faostat.csv")
    if not fa.empty:
        piv = fa.pivot_table(index="produit", columns="annee",
                             values="prix_mad_par_kg", aggfunc="first")
        y0, y1 = int(min(piv.columns)), int(max(piv.columns))
        ch = ((piv[y1] / piv[y0] - 1) * 100).dropna().sort_values(ascending=False)
        out["products"] = {"y0": y0, "y1": y1,
                           "items": [{"p": k, "c": round(float(x), 0)} for k, x in ch.items()]}
        cat = fa[fa["annee"].isin([y0, y1])]
        contrib = []
        for c, g in cat.groupby("categorie"):
            w = g.pivot_table(index="produit", columns="annee",
                              values="prix_mad_par_kg", aggfunc="first").dropna()
            if len(w):
                contrib.append({"cat": c,
                                "c": round(float(np.exp(np.log(w[y1] / w[y0]).mean()) - 1) * 100, 1)})
        out["categories"] = sorted(contrib, key=lambda x: x["c"])

    hz = _read("serie_logement.csv")
    if not hz.empty:
        out["housing"] = {"dates": hz["date"].astype(str).tolist(),
                          "v": [round(float(x), 1) for x in hz["loyer_dh_m2"]]}
    return out


def main() -> None:
    if not PAGE.exists():
        print("docs/index.html absent — rien à régénérer.")
        return
    data = build_data()
    line = "const DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    html = PAGE.read_text(encoding="utf-8")
    new_html, n = re.subn(r"const DATA = \{.*\};", lambda _: line, html, count=1)
    if n != 1:
        raise SystemExit("Bloc `const DATA = {...};` introuvable dans docs/index.html")
    PAGE.write_text(new_html, encoding="utf-8")
    days = len(data.get("daily", {}).get("dates", []))
    print(f"docs/index.html régénéré ({days} jours dans l'indice quotidien).")


if __name__ == "__main__":
    main()
