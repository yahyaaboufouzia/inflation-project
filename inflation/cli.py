"""Command-line entry points.

    inflation-scrape [--demo] [--db PATH]     scrape prices once
    inflation-index  [--base YYYY-MM-DD]      (re)compute the daily index

Also runnable as `python -m inflation.cli scrape` / `... index`.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from . import pipeline
from .index import compute_index
from .storage import repository as repo


def scrape(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Scrape prices for the basket.")
    ap.add_argument("--demo", action="store_true", help="use the offline synthetic scraper")
    ap.add_argument("--db", default=str(repo.DEFAULT_DB))
    ap.add_argument("--config", default="config")
    args = ap.parse_args(argv)

    n = pipeline.run_scrape(db_path=args.db, config_dir=args.config, use_demo=args.demo)
    print(f"Stored {n} price observations.")


def build_index(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Compute the daily inflation index.")
    ap.add_argument("--db", default=str(repo.DEFAULT_DB))
    ap.add_argument("--base", help="base day (index = 100), format YYYY-MM-DD")
    ap.add_argument("--elementary", default="jevons", choices=["jevons", "carli"])
    ap.add_argument("--export", help="also write the index to this CSV path")
    args = ap.parse_args(argv)

    engine = repo.get_engine(args.db)
    df = repo.observations_df(engine)
    base = date.fromisoformat(args.base) if args.base else None
    out = compute_index(df, base_day=base, elementary=args.elementary)

    if out.empty:
        print("No data yet — run `inflation-scrape --demo` first.")
        return

    repo.save_index(engine, out)
    if args.export:
        from pathlib import Path

        Path(args.export).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.export, index=False)
        print(f"Exported {len(out)} rows to {args.export}")
    last = out.iloc[-1]
    change = last["value"] - 100.0
    print(
        f"Index on {last['day']}: {last['value']:.2f} "
        f"({change:+.2f}% vs base {last['base_day']}) over {len(out)} days."
    )


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m inflation.cli {scrape,index} [options]")
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "scrape":
        scrape(rest)
    elif cmd == "index":
        build_index(rest)
    else:
        print(f"unknown command: {cmd!r} (expected 'scrape' or 'index')")


if __name__ == "__main__":
    main()
