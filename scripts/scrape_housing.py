"""Housing component: median rent (MAD per m² per month) from Mubawab.

Housing is the heaviest non-food weight in any CPI, but no public historical
series exists for Morocco. Rental listings are a usable proxy: we normalise by
surface (MAD/m²) and take the MEDIAN across listings, which is robust to the
changing mix of what happens to be listed on a given day.

    from scrape_housing import median_rent_dh_m2
"""
from __future__ import annotations

import re
import statistics
import warnings

import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

BASE = "https://www.mubawab.ma/fr/sc/appartements-a-louer"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Accept": "text/html", "Accept-Language": "fr-FR,fr;q=0.9",
}
RENT_MIN, RENT_MAX = 1000, 60000      # MAD/month sanity bounds
SURF_MIN, SURF_MAX = 20, 600          # m² sanity bounds


def _num(text: str) -> int | None:
    s = re.sub(r"[^\d]", "", text.split(",")[0])
    return int(s) if s else None


def median_rent_dh_m2(pages: int = 3) -> tuple[float | None, int, str]:
    """Return (median MAD/m², n_listings, source_url)."""
    values = []
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for page in range(1, pages + 1):
            url = BASE if page == 1 else f"{BASE}:p:{page}"
            try:
                r = client.get(url)
            except Exception:
                break
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "lxml")
            for pt in soup.select(".priceTag"):
                node = pt
                for _ in range(6):
                    node = node.parent
                    if node is None or re.search(r"m[²2]", node.get_text()):
                        break
                if node is None:
                    continue
                price = _num(pt.get_text())
                m = re.search(r"(\d{2,4})\s*m[²2]", node.get_text())
                surf = int(m.group(1)) if m else None
                if (price and surf and RENT_MIN <= price <= RENT_MAX
                        and SURF_MIN <= surf <= SURF_MAX):
                    values.append(price / surf)
    if not values:
        return None, 0, BASE
    return round(statistics.median(values), 1), len(values), BASE


if __name__ == "__main__":
    med, n, url = median_rent_dh_m2()
    print(f"Loyer médian: {med} DH/m²/mois (n={n})")
