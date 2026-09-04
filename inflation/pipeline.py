"""Orchestration: scrape every active product, clean, and store.

This is the single entry point the nightly job calls — identical whether it
runs on your laptop (Task Scheduler) or in GitHub Actions. It scrapes, it does
not compute the index; that is a separate, pure step (see index.py) so the two
concerns stay decoupled.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from .config import load_basket, load_sites
from .scrapers.registry import get_scraper
from .storage import repository as repo


def run_scrape(
    db_path: Path | str = repo.DEFAULT_DB,
    config_dir: Path | str = "config",
    use_demo: bool = False,
    polite: bool = True,
) -> int:
    """Scrape all active products once and persist the observations.

    Parameters
    ----------
    use_demo : force the offline synthetic scraper for every product, ignoring
               their configured site. Handy for CI and local demos.
    polite   : sleep `site.delay` seconds between real requests.

    Returns the number of price observations stored.
    """
    basket = load_basket(config_dir)
    sites = load_sites(config_dir)

    engine = repo.get_engine(db_path)
    repo.init_db(engine)
    repo.sync_catalog(engine, basket)

    scrapers: dict[str, object] = {}
    rows: list[dict] = []

    for product in basket.products:
        if not product.active:
            continue
        site = "demo" if use_demo else product.site
        if site not in scrapers:
            scrapers[site] = get_scraper(site, sites.get(site))
        scraper = scrapers[site]

        try:
            result = scraper.fetch_price(product)
        except Exception as exc:  # one bad product must not kill the run
            print(f"  ! {product.id} ({site}): {exc}")
            continue

        if result.price is not None and result.in_stock:
            rows.append(
                {
                    "product_id": result.product_id,
                    "price": result.price,
                    "currency": result.currency,
                    "in_stock": result.in_stock,
                    "scraped_at": result.scraped_at or datetime.now(),
                    "source_site": site,
                    "source_url": product.url,
                }
            )

        if polite and site != "demo":
            site_cfg = sites.get(site)
            if site_cfg:
                time.sleep(site_cfg.delay)

    return repo.add_observations(engine, rows)
