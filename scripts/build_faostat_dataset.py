"""Build a real, verifiable Morocco price dataset from FAOSTAT.

Source: FAOSTAT — "Prices: Producer Prices" (domain PP), bulk download (no key).
These are the ANNUAL producer (farm-gate) prices Moroccan producers received,
per commodity, in local currency (MAD) per tonne — converted here to MAD/kg.
Real, official, and downloadable, going back to the 1990s.

Note: producer prices are NOT retail/supermarket prices (retail is higher and
includes margins), but they are the densest free per-product price series
available for Morocco and track food inflation well.

Output: data/prix_maroc_faostat.csv — one row per (product, year) with the
price, a USD cross-check, the FAOSTAT item code, a data-quality flag, and a
source URL so every value can be verified.

    python scripts/build_faostat_dataset.py
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pandas as pd

BULK_URL = "https://bulks-faostat.fao.org/production/Prices_E_All_Data_(Normalized).zip"
OUT = Path("data/prix_maroc_faostat.csv")

# FAOSTAT item name -> (French label, category). Heavily consumed Moroccan
# staples that carry weight in food inflation.
STAPLES = {
    "Wheat": ("Blé", "Céréales"),
    "Barley": ("Orge", "Céréales"),
    "Maize (corn)": ("Maïs", "Céréales"),
    "Potatoes": ("Pommes de terre", "Légumes"),
    "Tomatoes": ("Tomates", "Légumes"),
    "Onions and shallots, dry (excluding dehydrated)": ("Oignons", "Légumes"),
    "Carrots and turnips": ("Carottes", "Légumes"),
    "Chillies and peppers, green (Capsicum spp. and Pimenta spp.)": ("Poivrons", "Légumes"),
    "Lentils, dry": ("Lentilles", "Légumineuses"),
    "Chick peas, dry": ("Pois chiches", "Légumineuses"),
    "Beans, dry": ("Haricots secs", "Légumineuses"),
    "Oranges": ("Oranges", "Fruits"),
    "Tangerines, mandarins, clementines": ("Clémentines", "Fruits"),
    "Apples": ("Pommes", "Fruits"),
    "Bananas": ("Bananes", "Fruits"),
    "Olives": ("Olives", "Fruits"),
    "Hen eggs in shell, fresh": ("Œufs", "Produits animaux"),
    "Meat of chickens, fresh or chilled": ("Poulet", "Viandes"),
    "Meat of cattle with the bone, fresh or chilled": ("Bœuf", "Viandes"),
    "Meat of sheep, fresh or chilled": ("Mouton", "Viandes"),
    "Raw milk of cattle": ("Lait de vache", "Produits animaux"),
}
FIRST_YEAR = 2000


def main() -> None:
    print("Downloading FAOSTAT producer prices (bulk)...")
    r = httpx.get(BULK_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=300,
                  follow_redirects=True)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    csv_name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    df = pd.read_csv(z.open(csv_name), encoding="latin-1", low_memory=False)

    df = df[df["Area"] == "Morocco"]
    lcu = (df[df["Element"] == "Producer Price (LCU/tonne)"]
           [["Item", "Item Code (CPC)", "Year", "Value", "Flag"]]
           .rename(columns={"Value": "mad_tonne"}))
    usd = (df[df["Element"] == "Producer Price (USD/tonne)"]
           [["Item", "Year", "Value"]].rename(columns={"Value": "usd_tonne"}))

    m = lcu.merge(usd, on=["Item", "Year"], how="left")
    m = m[m["Item"].isin(STAPLES) & (m["Year"] >= FIRST_YEAR)].copy()
    m["produit"] = m["Item"].map(lambda x: STAPLES[x][0])
    m["categorie"] = m["Item"].map(lambda x: STAPLES[x][1])
    m["prix_mad_par_kg"] = (m["mad_tonne"] / 1000).round(2)
    m["prix_usd_par_kg"] = (m["usd_tonne"] / 1000).round(3)
    m["source"] = "FAOSTAT - Producer Prices (Maroc)"
    m["source_url"] = "https://www.fao.org/faostat/fr/#data/PP"

    out = (m[["produit", "categorie", "Year", "prix_mad_par_kg", "prix_usd_par_kg",
              "Item", "Item Code (CPC)", "Flag", "source", "source_url"]]
           .rename(columns={"Year": "annee", "Item": "produit_faostat",
                            "Item Code (CPC)": "code_produit_cpc",
                            "Flag": "drapeau_qualite"})
           .sort_values(["categorie", "produit", "annee"])
           .reset_index(drop=True))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Wrote {OUT}: {len(out)} rows, {out['produit'].nunique()} products, "
          f"{out['annee'].min()}-{out['annee'].max()}")


if __name__ == "__main__":
    main()
