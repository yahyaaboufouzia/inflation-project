"""Regression tests for price parsing and sanity checks."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scrape_aswak_catalog import parse_price, plausible  # noqa: E402


def test_parse_price_french_format():
    assert parse_price("1 299,00 DH") == 1299.0
    assert parse_price("8,50 Dh") == 8.5
    assert parse_price("19,95") == 19.95


def test_parse_price_no_number():
    assert parse_price("Rupture de stock") is None


def test_plausible_accepts_realistic():
    assert plausible(19.95)
    assert plausible(3.5)
    assert plausible(345.8)


def test_plausible_rejects_absurd():
    # the exact failures the reviewer warned about: 0 and 999999
    assert not plausible(0)
    assert not plausible(999999)
    assert not plausible(None)
