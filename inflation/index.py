"""The price index — the intellectual core of the project.

We build a daily index the way statistical agencies do, in two stages:

1. **Elementary aggregation** (within a category): combine the price relatives
   p_t / p_0 of the products in a category. Default is the **Jevons** index
   (geometric mean of relatives), which is what modern CPIs use at this level
   because it is not distorted by a single product's large swing.

2. **Weighted aggregation** (across categories): combine category indices with
   their budget weights. This is the **Laspeyres** step and it is where the
   weighting matters — cheap TVs must not cancel out expensive cooking oil,
   because a household does not spend equally on both.

        I_t = 100 x  sum_c ( w_c * I_c,t )

`simple_laspeyres` is a flat, product-level version kept for teaching and for
the worked example documented in the README.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


def _daily_price(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse many intraday observations into one price per product per day.

    Uses the median, so a single glitchy scrape cannot move the daily price.
    """
    d = df.copy()
    d["day"] = pd.to_datetime(d["scraped_at"]).dt.date
    return (
        d.groupby(["product_id", "category_id", "category_weight", "day"])["price"]
        .median()
        .reset_index()
    )


def compute_index(
    df: pd.DataFrame,
    base_day: date | None = None,
    elementary: str = "jevons",
) -> pd.DataFrame:
    """Build the daily index from raw observations.

    Parameters
    ----------
    df : DataFrame with product_id, price, scraped_at, category_id,
         category_weight (as returned by repository.observations_df).
    base_day : the day the index equals 100. Defaults to the earliest day.
    elementary : 'jevons' (geometric mean) or 'carli' (arithmetic mean).

    Returns a DataFrame with columns: day, value, base_day.
    """
    if df.empty:
        return pd.DataFrame(columns=["day", "value", "base_day"])

    daily = _daily_price(df)
    if base_day is None:
        base_day = daily["day"].min()

    # anchor every product to its price on the base day
    base = (
        daily.loc[daily["day"] == base_day, ["product_id", "price"]]
        .rename(columns={"price": "p0"})
    )
    daily = daily.merge(base, on="product_id", how="inner")
    daily["relative"] = daily["price"] / daily["p0"]

    # stage 1 — elementary index per (category, day)
    grouped = daily.groupby(["category_id", "category_weight", "day"])["relative"]
    if elementary == "jevons":
        cat = grouped.apply(lambda r: float(np.exp(np.log(r).mean())))
    elif elementary == "carli":
        cat = grouped.mean()
    else:
        raise ValueError(f"unknown elementary index: {elementary!r}")
    cat = cat.reset_index(name="cat_relative")

    # stage 2 — Laspeyres aggregation across categories.
    # np.average renormalises over whichever categories are present that day.
    out = (
        cat.groupby("day")
        .apply(
            lambda g: 100.0
            * float(np.average(g["cat_relative"], weights=g["category_weight"])),
            include_groups=False,
        )
        .reset_index(name="value")
    )
    out["base_day"] = base_day
    return out.sort_values("day").reset_index(drop=True)


def compute_monthly_index(
    df: pd.DataFrame, coverage: float = 0.7, elementary: str = "jevons"
) -> pd.DataFrame:
    """Monthly index, robust to sparse/irregular observations (e.g. archives).

    Real archived snapshots do not land on a regular grid, so we:
      1. take one price per product per month (median of that month's snapshots)
      2. forward-fill each product onto a monthly grid — a price is assumed to
         hold until the next observation (the standard assumption)
      3. anchor the base at the first month whose coverage reaches `coverage`
         (so the base is well populated), then Jevons within category and
         Laspeyres across categories, exactly like the daily index.

    Returns columns day (month), value, base_day — same shape as compute_index.
    """
    empty = pd.DataFrame(columns=["day", "value", "base_day"])
    if df.empty:
        return empty

    d = df.copy()
    d["month"] = pd.to_datetime(d["scraped_at"]).dt.to_period("M").dt.to_timestamp()
    cat_of = d.groupby("product_id")["category_id"].first()
    weight_of = d.groupby("product_id")["category_weight"].first()

    monthly = d.groupby(["product_id", "month"])["price"].median().reset_index()
    grid = pd.date_range(monthly["month"].min(), monthly["month"].max(), freq="MS")
    wide = monthly.pivot(index="month", columns="product_id", values="price")
    wide = wide.reindex(grid).ffill()  # carry last known price forward

    # anchor the base at a well-covered month, but keep the WHOLE history:
    # months before the base are shown too (indexed to the base), using
    # whichever products were already archived then.
    cov = wide.notna().sum(axis=1) / wide.shape[1]
    eligible = cov[cov >= coverage].index
    base_month = eligible[0] if len(eligible) else cov.idxmax()

    p0 = wide.loc[base_month]
    valid = p0.dropna().index
    if len(valid) == 0:
        return empty
    rel = wide[valid].divide(p0[valid])

    out = []
    for month, row in rel.iterrows():
        r = row.dropna()
        if r.empty:
            continue
        cat_vals: dict[str, list[float]] = {}
        cat_w: dict[str, float] = {}
        for pid, val in r.items():
            c = cat_of[pid]
            cat_vals.setdefault(c, []).append(val)
            cat_w[c] = weight_of[pid]
        if elementary == "jevons":
            cat_rel = {c: float(np.exp(np.mean(np.log(v)))) for c, v in cat_vals.items()}
        else:
            cat_rel = {c: float(np.mean(v)) for c, v in cat_vals.items()}
        weights = np.array([cat_w[c] for c in cat_rel])
        values = np.array(list(cat_rel.values()))
        out.append({
            "day": month.date(),
            "value": 100.0 * float(np.average(values, weights=weights)),
            "base_day": base_month.date(),
        })
    return pd.DataFrame(out).sort_values("day").reset_index(drop=True)


def simple_laspeyres(
    relatives: dict[str, float], weights: dict[str, float]
) -> float:
    """Flat, product-level Laspeyres index (weights renormalised to the items given).

    Reproduces the worked example in the README:
        oil +7.9%, flour +2.4%, coffee 0%, TV -5% with budget weights
        0.35 / 0.40 / 0.15 / 0.10  ->  index ~= 103.21  (i.e. +3.2%).
    """
    total_w = sum(weights[k] for k in relatives)
    weighted = sum(weights[k] * relatives[k] for k in relatives)
    return 100.0 * weighted / total_w


def top_movers(df: pd.DataFrame, base_day: date | None = None, n: int = 5) -> pd.DataFrame:
    """Products whose price moved the most since the base day (biggest signal)."""
    if df.empty:
        return pd.DataFrame(columns=["product_name", "p0", "latest", "change_pct"])

    daily = _daily_price(df)
    if base_day is None:
        base_day = daily["day"].min()
    latest_day = daily["day"].max()

    names = df[["product_id", "product_name"]].drop_duplicates()
    base = daily.loc[daily["day"] == base_day, ["product_id", "price"]].rename(
        columns={"price": "p0"}
    )
    last = daily.loc[daily["day"] == latest_day, ["product_id", "price"]].rename(
        columns={"price": "latest"}
    )
    m = base.merge(last, on="product_id").merge(names, on="product_id")
    m["change_pct"] = (m["latest"] / m["p0"] - 1.0) * 100.0
    m = m.reindex(m["change_pct"].abs().sort_values(ascending=False).index)
    return m[["product_name", "p0", "latest", "change_pct"]].head(n).reset_index(drop=True)
