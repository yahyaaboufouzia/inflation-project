"""Tests for the index math — the part that must be provably correct."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from inflation.index import compute_index, simple_laspeyres, top_movers


def test_simple_laspeyres_matches_worked_example():
    """The README example: oil/flour/coffee/TV -> index ~= 103.21 (+3.2%)."""
    relatives = {
        "oil": 96 / 89,     # +7.9%
        "flour": 43 / 42,   # +2.4%
        "coffee": 38 / 38,  # 0%
        "tv": 2280 / 2400,  # -5.0%
    }
    weights = {"oil": 0.35, "flour": 0.40, "coffee": 0.15, "tv": 0.10}
    assert simple_laspeyres(relatives, weights) == pytest.approx(103.21, abs=0.01)


def test_weighting_beats_naive_average():
    """Weighting the heavy staples pulls the index above the naive mean of +1.3%."""
    relatives = {"oil": 96 / 89, "flour": 43 / 42, "coffee": 1.0, "tv": 0.95}
    weights = {"oil": 0.35, "flour": 0.40, "coffee": 0.15, "tv": 0.10}
    naive = 100 * sum(relatives.values()) / len(relatives)
    weighted = simple_laspeyres(relatives, weights)
    assert weighted > naive  # 103.2 > 101.3


def _toy_observations() -> pd.DataFrame:
    """Two products in two equally... no — differently weighted categories."""
    rows = [
        # product A, category X (weight 0.6)
        ("A", "X", 0.6, "2026-01-01", 100.0),
        ("A", "X", 0.6, "2026-01-02", 110.0),
        # product B, category Y (weight 0.4)
        ("B", "Y", 0.4, "2026-01-01", 200.0),
        ("B", "Y", 0.4, "2026-01-02", 190.0),
    ]
    df = pd.DataFrame(
        rows, columns=["product_id", "category_id", "category_weight", "scraped_at", "price"]
    )
    df["scraped_at"] = pd.to_datetime(df["scraped_at"])
    df["product_name"] = df["product_id"]
    return df


def test_compute_index_base_is_100():
    out = compute_index(_toy_observations(), base_day=date(2026, 1, 1))
    first = out.loc[out["day"] == date(2026, 1, 1), "value"].iloc[0]
    assert first == pytest.approx(100.0)


def test_compute_index_applies_category_weights():
    # A: +10% (w=0.6), B: -5% (w=0.4)
    #   -> 100 * (0.6*1.10 + 0.4*0.95) = 104.0
    out = compute_index(_toy_observations(), base_day=date(2026, 1, 1))
    day2 = out.loc[out["day"] == date(2026, 1, 2), "value"].iloc[0]
    assert day2 == pytest.approx(104.0)


def test_compute_index_empty_is_safe():
    empty = pd.DataFrame(
        columns=["product_id", "category_id", "category_weight", "scraped_at", "price"]
    )
    assert compute_index(empty).empty


def test_top_movers_ranks_by_absolute_change():
    movers = top_movers(_toy_observations(), base_day=date(2026, 1, 1), n=2)
    # A moved +10%, B moved -5%; A ranks first (bigger magnitude)
    assert movers.iloc[0]["product_name"] == "A"
    assert movers.iloc[0]["change_pct"] == pytest.approx(10.0)
