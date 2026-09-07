"""Build a large product catalog from Aswak Assalam category listings.

Scraping category pages (not individual products) is efficient: one request
returns ~12-40 products with their price and URL. The catalog defines the
universe for the DAILY index; the daily collector re-reads the same category
pages and matches products by URL.

Output: data/aswak_catalog.csv (product_id, produit, categorie, unite, url, prix)

    python scripts/scrape_aswak_catalog.py
"""
from __future__ import annotations

import random
import re
import time
from pathlib import Path

import httpx
import pandas as pd
from bs4 import BeautifulSoup

BASE = "https://aswakassalam.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120",
    "Accept": "text/html", "Accept-Language": "fr-FR,fr;q=0.9",
}
MAX_PAGES = 3          # per category
PRICE_MIN, PRICE_MAX = 0.1, 100000.0   # sanity bounds (MAD) — reject 0 / 999999
OUT = Path("data/aswak_catalog.csv")

client = httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)


def fetch(url: str, attempts: int = 4) -> httpx.Response | None:
    """GET with exponential backoff + jitter; backs off on 403/429/503."""
    for i in range(attempts):
        try:
            r = client.get(url)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429, 503):
                time.sleep(2 ** i + random.uniform(0, 1.5))
                continue
            return r
        except Exception:
            time.sleep(2 ** i + random.uniform(0, 1.5))
    return None


def plausible(price: float | None) -> bool:
    return price is not None and PRICE_MIN <= price <= PRICE_MAX


def parse_unit(name: str) -> str:
    m = re.search(r"\d+\s?(?:x\s?\d+)?\s?(?:kg|g|l|cl|ml|u)\b", name.lower())
    return m.group(0).replace(" ", "") if m else ""


def parse_price(text: str) -> float | None:
    m = re.search(r"\d[\d\s.]*,\d{2}", text) or re.search(r"\d[\d\s.]*", text)
    if not m:
        return None
    s = m.group(0).replace(" ", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def categories() -> list[str]:
    r = fetch(BASE + "/")
    if r is None:
        print("  ! page d'accueil inaccessible (bloqué ?)")
        return []
    soup = BeautifulSoup(r.text, "lxml")
    slugs = []
    for a in soup.select('a[href*="/product-category/"]'):
        m = re.search(r"/product-category/([^/?]+)/", a.get("href", ""))
        if m and m.group(1) not in slugs:
            slugs.append(m.group(1))
    return slugs


def scrape_category(slug: str) -> list[dict]:
    rows, dropped = [], 0
    for page in range(1, MAX_PAGES + 1):
        url = f"{BASE}/product-category/{slug}/" + (f"page/{page}/" if page > 1 else "")
        r = fetch(url)
        if r is None or r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select("li.product")
        if not items:
            if page == 1:   # 200 but no products = possible markup change / block
                print(f"  ! {slug}: 0 produit en page 1 (structure changée ou bloqué ?)")
            break
        for li in items:
            a = li.select_one('a[href*="/produit/"]')
            title = li.select_one(".product-loop-title, h2, h3")
            amounts = li.select(".price .woocommerce-Price-amount")
            if not a or not amounts:
                continue
            price = parse_price(amounts[-1].get_text(" ", strip=True))
            if not plausible(price):   # reject 0 / 999999 / unparsable
                dropped += 1
                continue
            name = title.get_text(" ", strip=True) if title else a.get_text(" ", strip=True)
            rows.append({
                "product_id": a["href"].rstrip("/").split("/")[-1],
                "produit": name,
                "categorie": slug,
                "unite": parse_unit(name),
                "url": a["href"],
                "prix": price,
            })
        time.sleep(1.5)
    if dropped:
        print(f"  · {slug}: {dropped} prix aberrants ignorés")
    return rows


def main() -> None:
    cats = categories()
    print(f"{len(cats)} catégories: {cats}")
    all_rows = []
    for i, slug in enumerate(cats, 1):
        rows = scrape_category(slug)
        print(f"[{i:2}/{len(cats)}] {slug:28} {len(rows)} produits", flush=True)
        all_rows += rows
        time.sleep(2.0)

    df = pd.DataFrame(all_rows).drop_duplicates("product_id")
    df = df[df["prix"].notna()].reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8")
    print(f"\nCatalogue: {len(df)} produits uniques -> {OUT}")


if __name__ == "__main__":
    main()
