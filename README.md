# 📈 Morocco Inflation Tracker

**An independent inflation index for Morocco, built from real online prices — and compared against the official HCP consumer price index.**

Inspired by MIT's [Billion Prices Project](https://thebillionpricesproject.com/): official inflation in Morocco is published once a month by a public body, with no way for an outsider to verify the calculation. This project produces its *own* measure and asks a simple question — **do the two tell the same story?**

Prices are scraped live from **Aswak Assalam** (a Moroccan hypermarket chain), and back-history is reconstructed from archived snapshots of the same pages via the **Wayback Machine** — so every value is real and carries its source URL.

<!-- Add screenshots / a Streamlit Cloud badge here once deployed -->

---

## Why this is interesting

The official index (HCP) is measured the classic way: field agents visit shops, record the price of a fixed basket of goods, and compare month over month. It is solid, but **slow** (monthly), **costly** (people on the ground), and **opaque** (you see the result, not the readings).

A scraper does, for free and every night, what the agents do once a month. After two months you have something almost no one else has: **a daily price history for Morocco.**

This is exactly the method Cavallo & Rigobon used at MIT to show Argentina was under-reporting its inflation — official ~10%/yr, their scraped index ~twice that. Same idea, applied to Morocco.

## How the index is built

Naively averaging price changes is **wrong**: a household buys cooking oil every week and a TV every eight years. So each product is weighted by its share of the household budget. Formally, a **Laspeyres index**:

```
I_t = 100 × Σ_c  w_c · (I_c,t)
```

where `w_c` is the budget weight of category `c` and `I_c,t` is that category's elementary index (a **Jevons** geometric mean of price relatives `p_t / p_0`).

**Worked example** (documented and unit-tested in [`tests/test_index.py`](tests/test_index.py)):

| Product | Change | Weight | Contribution |
|---|--:|--:|--:|
| Cooking oil 5L | +7.9% | 0.35 | +2.77 |
| Flour 5kg | +2.4% | 0.40 | +0.96 |
| Coffee 250g | 0% | 0.15 | 0 |
| TV 43" | −5.0% | 0.10 | −0.50 |
| **Index** | | **1.00** | **≈ +3.2%** |

A naive average would say +1.3%. Weighting says +3.2%. That gap is the whole point.

## Architecture

```
   E-commerce sites (Jumia, Marjane, …)
            │   every night
            ▼
      [ Scrapers ]  ───►  raw snapshots (audit trail)
            │
            ▼
      [ Cleaning ]   "1 299,00 DH" → 1299.0 · in stock?
            │
            ▼
      [ SQLite ]   price_observations  (append-only time series)
            │
            ├──►  [ Laspeyres index ]  ──►  index_values
            │
            └──►  [ Official HCP CPI ]
                        │
                        ▼
              [ Dashboard: 2 curves + gap analysis ]
```

**Design principles.** Collection and calculation are decoupled — scrapers only record price observations, the index is a pure function on top, so you can recompute with different weights or a different basket **without re-scraping**. The basket and weights live in versioned YAML, not in code.

```
inflation/          the Python package
  config.py         load & validate basket + weights (pydantic)
  scrapers/         base.py · static.py · demo.py · registry.py
  storage/          models.py · repository.py  (SQLAlchemy + SQLite)
  cleaning.py       price string → float
  index.py          Laspeyres / Jevons index  ← the core
  official.py       load & rebase the HCP CPI
  pipeline.py       scrape → clean → store (one entry point)
  cli.py            inflation-scrape · inflation-index
config/             basket.yaml · weights.yaml · sites.yaml
dashboard/app.py    Streamlit dashboard
scripts/
  backfill_wayback.py  reconstruct real history from web archives
  run_daily.py         one daily collection run (used by the nightly job)
  seed_demo.py         optional offline synthetic history
tests/              index math is unit-tested
.github/workflows/  nightly scrape + CI
```

## Quickstart

```bash
git clone https://github.com/yahyaaboufouzia/inflation-project.git
cd inflation-project

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e ".[dashboard,dev]"

python scripts/backfill_wayback.py   # reconstruct real history from web archives
inflation-scrape                     # add today's real prices (Aswak Assalam)
inflation-index --export data/daily/index.csv
streamlit run dashboard/app.py       # open the dashboard
```

The committed `data/observations.csv` already contains real history, so you can
open the dashboard straight away. Run the tests with `pytest -q`.

## How the data is collected

- **Live prices** come from **Aswak Assalam** (`aswakassalam.com`), a WooCommerce
  store whose prices sit in the HTML — scraped with `httpx` + BeautifulSoup. The
  bigger sites (Jumia, Marjane, Avito, Electroplanet) return HTTP 403 to bots.
- **History** is reconstructed from the **Wayback Machine**: each product page
  has archived snapshots going back to 2022, and we read the price from each.
- **Provenance**: every observation stores its `source_site` and `source_url`,
  so any value can be traced back to the exact page it came from.
- **Frequency**: because snapshots are irregular, the index is aggregated
  **monthly** (last known price carried forward), which also makes it directly
  comparable to the monthly HCP index.
- **Regulated / published prices** (bread, sugar, butane gas, fuel) are not sold
  online and will be added later from official sources.

The nightly [GitHub Actions workflow](.github/workflows/nightly.yml) re-runs the
collection and commits the refreshed data back, so the history is versioned and
public. Aswak Assalam may block cloud runners, so a local machine (Task
Scheduler) running `scripts/run_daily.py` is the reliable collector.

## Roadmap

- [ ] Expand the basket with more Aswak Assalam products
- [ ] Add regulated/published prices (fuel, butane, bread) from official sources
- [ ] A Playwright-based scraper for the JavaScript sites (Marjane, Jumia)
- [ ] Deploy the dashboard to Streamlit Community Cloud (public link)
- [ ] Written analysis of the gap vs the HCP index

## Credits

Methodology after Alberto Cavallo & Roberto Rigobon, *"The Billion Prices Project: Using Online Prices for Measurement and Research"* (Journal of Economic Perspectives, 2016). Official data: Haut-Commissariat au Plan (HCP), Morocco.

## License

MIT — see [LICENSE](LICENSE).
