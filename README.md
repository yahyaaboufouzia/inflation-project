# 📈 Morocco Inflation Tracker

**An independent, daily inflation index for Morocco — built from real online prices, validated against ground truth, and compared to the official CPI.**

[![tests](https://github.com/yahyaaboufouzia/inflation-project/actions/workflows/tests.yml/badge.svg)](https://github.com/yahyaaboufouzia/inflation-project/actions/workflows/tests.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![basket](https://img.shields.io/badge/basket-352%20products-brightgreen)
![data](https://img.shields.io/badge/data-updated%20daily-orange)

Inspired by MIT's [Billion Prices Project](https://thebillionpricesproject.com/): official inflation in Morocco is published once a month by a public body, with no way for an outsider to verify it. This project builds its **own** measure — **daily**, from real prices, with every value traceable to its source — and asks: *do the two tell the same story?*

---

## What it does

| | |
|---|---|
| 🗓️ **Daily index** | Scrapes **350+ items** every day across CPI-style divisions — food, hygiene & cleaning (**Aswak Assalam**) **and housing** (rent in MAD/m², **Mubawab**) — weighted like a CPI (Food 45%, Housing 22%, …). A new point is added each day. |
| 📅 **Long-run comparison** | A 21-staple index from **FAOSTAT** producer prices (2000–2024) vs the **official Morocco food CPI**, with three fairness corrections. |
| 🇺🇸 **Method validation** | The same method applied to **real US retail prices** (BLS/FRED) reproduces the official US food CPI with a **correlation of 0.99** — proving the method works where good data exists. |
| 🔎 **Full provenance** | Every price stores its `source_url`. Any value can be checked at its source. |

## The key idea

Naively averaging price changes is **wrong**: a household buys cooking oil every week and a TV every eight years. Each product is weighted by its share of the budget. Formally, a two-stage index (like real statistical agencies):

**1. Elementary index per category** — geometric mean of price relatives (**Jevons**):

```
I(c,t) = ( Π  p(i,t)/p(i,0) ) ^ (1/n)
```

**2. Overall index** — budget-weighted average across categories (**Laspeyres**):

```
I(t) = 100 × Σ_c  w(c) · I(c,t)
```

## Method validation (the important part)

Anyone can build an index — the question is whether it's *right*. So the method is tested where the truth is known: the **USA**, which publishes decades of real retail prices (BLS "Average Price" series via FRED). Feeding those into **our exact method** and comparing to the **official US food CPI** (13 products, 1980–2026):

| Metric | Value |
|---|---|
| Correlation on **year-over-year rates** | **0.72** |
| Mean absolute error on annual rates | **2.6 pts** |
| Cumulative inflation (ours vs official) | +208% vs +301% |

> ⚠️ **Not** the level correlation (0.99). Correlating two rising non-stationary series is spurious (Granger–Newbold): even a made-up `exp(0.03·t)` trend scores 0.99 against the CPI. The honest test is on **stationary year-over-year rates**, where 0.72 with just 13 products is a genuine result. The cumulative-level gap reflects a narrower basket than the official one.

The method **tracks** official inflation year to year where real retail data exists. Morocco's gap is therefore largely a **data problem** (only producer prices are public), not a method problem. See [`scripts/validate_usa.py`](scripts/validate_usa.py).

## Data & sources (all verifiable)

| Series | Source | File |
|---|---|---|
| Daily retail prices | Aswak Assalam (scraped) | `data/prix_actuels.csv`, `data/indice_quotidien.csv` |
| Historical staple prices | [FAOSTAT — Producer Prices](https://www.fao.org/faostat/fr/#data/PP) | `data/prix_maroc_faostat.csv` |
| Official Morocco CPI (food + general) | [FAOSTAT — Consumer Price Indices](https://www.fao.org/faostat/fr/#data/CP) | `data/official/cpi_maroc_faostat.csv` |
| US retail prices + US CPI | [FRED / BLS](https://fred.stlouisfed.org/) | `data/validation_usa.csv` |

Why Aswak Assalam? Jumia, Marjane, Avito and Electroplanet block automated requests (HTTP 403); Aswak Assalam runs on WooCommerce with prices in the HTML — so it is the one large Moroccan retailer that is reliably scrapable today.

## Architecture

```
   Aswak Assalam (352 products, 11 categories)
          │  every day (Task Scheduler / GitHub Actions)
          ▼
   collect_daily.py  ──►  data/prix_actuels.csv   (dated, with source_url)
          │
          ▼
   build_daily_index.py  ──►  data/indice_quotidien.csv   (the daily curve)

   FAOSTAT + FRED  ──►  build_inflation_index.py / validate_usa.py
          │
          ▼
   Streamlit dashboard  (daily curve + long-run comparison + US validation)
```

**Design principle:** collection and calculation are decoupled. Scrapers only record dated observations; the index is a pure function on top, so weights, basket, or formula can change **without re-scraping**.

```
inflation/            core package (config, scrapers, storage, index, cleaning)
scripts/
  scrape_aswak_catalog.py   build the 352-product catalog
  collect_daily.py          scrape today's prices (run daily)
  build_daily_index.py      the daily index
  build_inflation_index.py  long-run index + official CPI
  validate_usa.py           method validation on the USA
  daily_collect.bat         Windows Task Scheduler entry point
dashboard/app.py      Streamlit dashboard (reads only CSVs)
data/                 versioned datasets (the audit trail)
tests/                unit tests for the index math
.github/workflows/    nightly collection + CI
```

## Quickstart

```bash
git clone https://github.com/yahyaaboufouzia/inflation-project.git
cd inflation-project

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -e ".[dashboard,dev]"

python scripts/build_inflation_index.py   # long-run index + official CPI
python scripts/validate_usa.py            # method validation (r = 0.99)
streamlit run dashboard/app.py            # open the dashboard
```

To grow the daily series, run the collector (schedule it once a day):

```bash
python scripts/collect_daily.py       # scrape today's 352 prices
python scripts/build_daily_index.py   # add today's point to the daily index
```

Run the tests with `pytest -q`.

## Daily automation

- **Local (reliable):** `scripts/daily_collect.bat` is registered in **Windows Task Scheduler** (runs at 20:00) — it collects, rebuilds the index, and commits + pushes. A Morocco IP is not blocked by the retailer.
- **Cloud:** the [nightly GitHub Actions workflow](.github/workflows/nightly.yml) does the same and refreshes the official series; the retailer may block cloud IPs, so the local runner is the primary collector.

Because prices are collected **forward** in time, the daily curve **grows one point per day** — a real daily history can't be reconstructed from the past, exactly as the Billion Prices Project did. **The daily series started in September 2026**, so it is still short; the long-run comparison and the US validation are what carry the analysis for now.

The daily index is a **chained, matched-sample** index (`I_t = I_{t-1} × Jevons(p_t / p_{t-1})` over products present on both days), so it is robust to products dropping in/out of a scrape and does not depend on an arbitrary base day.

**Promotions vs inflation.** Retail scraping mostly captures promotions, not underlying inflation. The scraper reads WooCommerce `<del>/<ins>` markup, so it stores both the **displayed** price (with promos) and the **reference** price (crossed-out), plus an `en_promo` flag. The index is published as **two series** — the gap between them *is* the promotional effect, so a rotation of promos can't be mistaken for inflation. (This is why range/variant grouping isn't needed: a promo on N flavours of one drink leaves the reference series flat regardless of N.)

## Honest limitations

- **Single retail source** (Aswak Assalam) — the others block scraping. Adding sources is the top priority for anti-fragility.
- **Producer vs retail:** the historical FAOSTAT series is farm-gate (more volatile, lower level than shelf prices); the daily scrape provides true retail going forward.
- **Official CPI is monthly** — it can't be daily; our daily curve is the added value.
- **Coverage:** the daily index now spans food, hygiene/cleaning and **housing** (rent). Housing uses rental *listings* (a composition-shifting proxy, normalised to MAD/m² and taken as a median). **Transport/fuel** is still missing — no scrapable public source found yet.

## Roadmap

- [x] Gap analysis: cumulative deviation vs the official index
- [x] Scraping robustness: retries with jitter + sanity checks (rejects 0 / 999999)
- [x] Category contribution chart (what drives inflation)
- [x] Promotion handling: displayed vs reference series, `en_promo` flag
- [ ] More sources: solve the anti-bot block on Jumia/Marjane (Playwright + stealth)
- [ ] Regulated prices (fuel, butane, bread, sugar) from official communiqués
- [ ] Deploy the dashboard publicly (Streamlit Community Cloud)
- [ ] A minimal REST API + monthly data releases

## Credits

Method after Alberto Cavallo & Roberto Rigobon, *"The Billion Prices Project: Using Online Prices for Measurement and Research"* (Journal of Economic Perspectives, 2016). Data: FAOSTAT, World Bank, US BLS/FRED, Aswak Assalam.

## License

MIT — see [LICENSE](LICENSE).
