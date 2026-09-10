"""Tests for the index math — the part that must be provably correct."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from inflation.index import (
    chained_matched_index,
    compute_index,
    compute_monthly_index,
    family_keys,
    index_from_relatives,
    simple_laspeyres,
    top_movers,
)


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


def test_monthly_index_forward_fills_and_weights():
    # A (cat X, w=0.6): Jan 100, [Feb missing -> ffill 100], Mar 110
    # B (cat Y, w=0.4): Jan 200, Feb 190, Mar 190
    rows = [
        ("A", "X", 0.6, "2026-01-15", 100.0),
        ("A", "X", 0.6, "2026-03-15", 110.0),
        ("B", "Y", 0.4, "2026-01-15", 200.0),
        ("B", "Y", 0.4, "2026-02-15", 190.0),
        ("B", "Y", 0.4, "2026-03-15", 190.0),
    ]
    df = pd.DataFrame(
        rows, columns=["product_id", "category_id", "category_weight", "scraped_at", "price"]
    )
    df["scraped_at"] = pd.to_datetime(df["scraped_at"])
    df["product_name"] = df["product_id"]

    out = compute_monthly_index(df).set_index("day")["value"]
    assert out.loc[date(2026, 1, 1)] == pytest.approx(100.0)   # base
    assert out.loc[date(2026, 2, 1)] == pytest.approx(98.0)    # A ffilled, B -5%
    assert out.loc[date(2026, 3, 1)] == pytest.approx(104.0)   # A +10%, B -5%


def test_index_from_relatives_weights_categories():
    # p1: everything at base (1.0) -> 100
    # p2: cat X (w0.6) +10%, cat Y (w0.4) -5% -> 100*(0.6*1.1 + 0.4*0.95) = 104
    rows = [
        ("p1", "X", 1.0), ("p1", "Y", 1.0),
        ("p2", "X", 1.10), ("p2", "Y", 0.95),
    ]
    df = pd.DataFrame(rows, columns=["period", "category", "relative"])
    out = index_from_relatives(df, weights={"X": 0.6, "Y": 0.4}).set_index("period")["value"]
    assert out["p1"] == pytest.approx(100.0)
    assert out["p2"] == pytest.approx(104.0)


def test_chained_matched_index():
    # A (cat X, w0.6), B (cat Y, w0.4)
    # d1->d2: A +10%, B -5%  -> link 1.04 -> 104
    # d2->d3: A  0%, B +10%  -> link 1.04 -> 108.16
    wide = pd.DataFrame(
        {"A": [100.0, 110.0, 110.0], "B": [200.0, 190.0, 209.0]},
        index=["d1", "d2", "d3"],
    )
    out = chained_matched_index(wide, {"A": "X", "B": "Y"}, {"X": 0.6, "Y": 0.4})
    vals = out.set_index("period")["value"]
    assert vals["d1"] == pytest.approx(100.0)
    assert vals["d2"] == pytest.approx(104.0)
    assert vals["d3"] == pytest.approx(108.16, abs=0.02)


def test_family_keys_group_variants_keep_singletons():
    fam = family_keys(["bomba-blue", "bomba-cherry", "bomba-classic", "bomba-mojito",
                       "farine-fleur-10kg"])
    assert fam["bomba-blue"] == fam["bomba-cherry"] == "bomba"   # 4 variants merged
    assert fam["farine-fleur-10kg"] == "farine-fleur-10kg"       # unique -> itself


def test_family_grouping_counts_a_range_once():
    # a 4-flavour range all at -14.9% must weigh the same as ONE product at -14.9%
    variants = pd.DataFrame(
        {"bomba-blue": [100.0, 85.1], "bomba-cherry": [100.0, 85.1],
         "bomba-classic": [100.0, 85.1], "bomba-mojito": [100.0, 85.1],
         "farine-1kg": [10.0, 10.0]},
        index=["d1", "d2"],
    )
    cat = {c: "X" for c in variants.columns}
    grouped = chained_matched_index(variants, cat, {"X": 1.0}, family_keys(variants.columns))

    single = pd.DataFrame({"bomba": [100.0, 85.1], "farine-1kg": [10.0, 10.0]},
                          index=["d1", "d2"])
    ungrouped = chained_matched_index(single, {"bomba": "X", "farine-1kg": "X"}, {"X": 1.0})

    assert (grouped.set_index("period")["value"]["d2"]
            == pytest.approx(ungrouped.set_index("period")["value"]["d2"]))


def test_chained_index_ignores_unmatched_product():
    # C appears only on d2 -> it must not create a jump on either link
    wide = pd.DataFrame(
        {"A": [100.0, 110.0], "C": [None, 50.0]},
        index=["d1", "d2"],
    )
    out = chained_matched_index(wide, {"A": "X", "C": "X"}, {"X": 1.0})
    assert out.set_index("period")["value"]["d2"] == pytest.approx(110.0)


def test_top_movers_ranks_by_absolute_change():
    movers = top_movers(_toy_observations(), base_day=date(2026, 1, 1), n=2)
    # A moved +10%, B moved -5%; A ranks first (bigger magnitude)
    assert movers.iloc[0]["product_name"] == "A"
    assert movers.iloc[0]["change_pct"] == pytest.approx(10.0)
