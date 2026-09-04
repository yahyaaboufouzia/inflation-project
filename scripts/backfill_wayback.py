"""Backfill REAL historical prices from the Wayback Machine (archive.org).

Live scraping only sees today. But archive.org has snapshotted these product
pages for years, so we can reconstruct genuine past prices. For each basket
product we list its archived snapshots (one per month at most), fetch each, and
extract the price exactly as the live scraper would. Every value keeps its
archived URL as its source.

Slow by nature (archive.org is slow) — run it once to seed history:

    python scripts/backfill_wayback.py
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inflation.cleaning import parse_price  # noqa: E402
from inflation.config import load_basket  # noqa: E402
from inflation.storage import repository as repo  # noqa: E402

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}
CDX = "http://web.archive.org/cdx/search/cdx"


def _get(url: str, **kwargs) -> httpx.Response | None:
    """GET with retries + backoff — archive.org throttles bursts of requests."""
    for attempt in range(4):
        try:
            return httpx.get(url, timeout=60, **kwargs)
        except Exception:
            time.sleep(3 * (attempt + 1))  # 3s, 6s, 9s
    return None


def snapshots(url: str) -> list[str]:
    """Timestamps of archived snapshots, at most one per month."""
    params = {"url": url, "output": "json", "collapse": "timestamp:6",
              "filter": "statuscode:200"}
    r = _get(CDX, params=params)
    if r is None:
        print(f"  ! CDX unreachable for {url}")
        return []
    try:
        return [row[1] for row in r.json()[1:]]
    except Exception:
        return []  # empty / non-JSON response = no snapshots


def price_from_snapshot(url: str, ts: str) -> float | None:
    # the id_ suffix returns the raw archived HTML without the Wayback toolbar
    archive_url = f"http://web.archive.org/web/{ts}id_/https://{url}"
    r = _get(archive_url, headers=HEADERS, follow_redirects=True)
    if r is None:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    block = soup.select_one(".summary .price") or soup.select_one("p.price")
    amounts = block.select(".woocommerce-Price-amount") if block else []
    return parse_price(amounts[-1].get_text(" ", strip=True)) if amounts else None


def main() -> None:
    basket = load_basket("config")
    engine = repo.get_engine()
    repo.init_db(engine)
    repo.sync_catalog(engine, basket)

    rows = []
    for i, product in enumerate(basket.products, 1):
        url = product.url.replace("https://", "").replace("http://", "")
        snaps = snapshots(url)
        got = 0
        for ts in snaps:
            price = price_from_snapshot(url, ts)
            if price is None:
                continue
            day = datetime.strptime(ts[:8], "%Y%m%d")
            rows.append({
                "product_id": product.id,
                "price": price,
                "in_stock": True,
                "scraped_at": day,
                "source_site": "aswak-wayback",
                "source_url": f"http://web.archive.org/web/{ts}/https://{url}",
            })
            got += 1
            time.sleep(1.0)  # be gentle with archive.org
        print(f"[{i:2}/{len(basket.products)}] {product.id:22} {got:2} archived prices", flush=True)
        time.sleep(3.0)  # pause between products so archive.org doesn't throttle

    n = repo.add_observations(engine, rows)
    print(f"\nStored {n} historical observations from the Wayback Machine.")


if __name__ == "__main__":
    main()
