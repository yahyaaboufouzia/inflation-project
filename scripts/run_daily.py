"""One daily collection run — the real cycle used by the nightly job.

    1. rebuild the DB from the committed history (data/observations.csv)
    2. scrape today's REAL prices and append them
    3. recompute the index
    4. re-export the versioned CSVs (observations + index)

Runs identically on a laptop (Task Scheduler) and in GitHub Actions. Because
prices are read from live pages, the values change over time on their own — no
synthetic drift. History accumulates one real day at a time.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inflation import pipeline  # noqa: E402
from inflation.config import load_basket  # noqa: E402
from inflation.index import compute_monthly_index  # noqa: E402
from inflation.storage import repository as repo  # noqa: E402

OBS_CSV = "data/observations.csv"
INDEX_CSV = "data/daily/index.csv"


def main() -> None:
    engine = repo.get_engine()
    repo.init_db(engine)
    repo.sync_catalog(engine, load_basket("config"))

    # restore prior history so today's scrape appends to it
    restored = repo.import_observations_csv(engine, OBS_CSV)

    # scrape today's real prices
    added = pipeline.run_scrape()

    # recompute and persist
    index = compute_monthly_index(repo.observations_df(engine))
    repo.save_index(engine, index)
    n_obs = repo.export_observations_csv(engine, OBS_CSV)
    index.to_csv(INDEX_CSV, index=False)

    print(f"Restored {restored} past observations, added {added} today.")
    print(f"History now holds {n_obs} observations over {len(index)} day(s).")
    if not index.empty:
        last = index.iloc[-1]
        print(f"Index on {last['day']}: {last['value']:.2f}")


if __name__ == "__main__":
    main()
