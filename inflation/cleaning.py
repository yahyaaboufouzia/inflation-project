"""Turn messy scraped text into clean numbers.

Moroccan e-commerce sites display prices in the French convention:
'.' groups thousands, ',' is the decimal separator, and a currency label
(DH / MAD / Dhs) trails the number — sometimes with non-breaking spaces.
"""
from __future__ import annotations

import re

_NUMBER = re.compile(r"\d[\d\s .,]*")


def parse_price(text: str | None) -> float | None:
    """Extract a price from arbitrary text, or None if there is no number.

    >>> parse_price("1 299,00 DH")
    1299.0
    >>> parse_price("89,90 Dhs")
    89.9
    >>> parse_price("Rupture de stock")
    """
    if text is None:
        return None
    match = _NUMBER.search(text)
    if not match:
        return None

    s = match.group(0).replace(" ", "").replace(" ", "").strip(" .,")
    if "," in s and "." in s:
        # both present -> '.' is the thousands separator, ',' the decimal
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        return round(float(s), 2)
    except ValueError:
        return None
