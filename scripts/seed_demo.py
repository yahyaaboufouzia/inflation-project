"""Populate the database with a few months of synthetic history.

Run once after cloning so the dashboard has something to show:

    python scripts/seed_demo.py

It uses the offline DemoScraper, so it needs no network and is deterministic.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

# allow running as a plain script (python scripts/seed_demo.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inflation.config import load_basket  # noqa: E402
from inflation.index import compute_index  # noqa: E402
from inflation.scrapers.demo import DemoScraper  # noqa: E402
from inflation.storage import repository as repo  # noqa: E402

DAYS = 75


def main() -> None:
    basket = load_basket("config")
    engine = repo.get_engine(repo.DEFAULT_DB)
    repo.init_db(engine)
    repo.sync_catalog(engine, basket)

    start = datetime.now() - timedelta(days=DAYS - 1)
    total = 0
    for i in range(DAYS):
        day = start + timedelta(days=i)
        scraper = DemoScraper(day=day)
        rows = []
        for product in basket.products:
            r = scraper.fetch_price(product)
            rows.append(
                {
                    "product_id": r.product_id,
                    "price": r.price,
                    "in_stock": r.in_stock,
                    "scraped_at": r.scraped_at,
                }
            )
        total += repo.add_observations(engine, rows)

    index = compute_index(repo.observations_df(engine))
    repo.save_index(engine, index)

    # export the versioned CSVs (the data history that gets committed to Git)
    n_obs = repo.export_observations_csv(engine, "data/observations.csv")
    index.to_csv("data/daily/index.csv", index=False)

    print(
        f"Seeded {total} observations over {DAYS} days "
        f"for {len(basket.products)} products."
    )
    print(f"Exported {n_obs} rows -> data/observations.csv")
    print("Exported index -> data/daily/index.csv")
    if not index.empty:
        last = index.iloc[-1]
        print(f"Latest index: {last['value']:.2f} ({last['value'] - 100:+.2f}%)")
        print(index.tail(5).to_string(index=False))


if __name__ == "__main__":
    main()
