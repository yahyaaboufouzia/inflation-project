"""Morocco Inflation Tracker — public dashboard.

Compares OUR food inflation index against the official Morocco food CPI, with
three methodological corrections (food-vs-food coverage, a smoothed series to
approximate sticky retail prices, and household food weights). Reads only
committed CSVs, so it deploys cleanly on Streamlit Community Cloud.

    streamlit run dashboard/app.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
RAW = "#93c5fd"      # our raw index (light)
OURS = "#2563eb"     # our smoothed index
FOOD = "#e07a3f"     # official food CPI
GEN = "#9ca3af"      # official general CPI

st.set_page_config(page_title="Morocco Inflation Tracker", page_icon="📈", layout="wide")


@st.cache_data(ttl=600)
def load_index() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "indice_inflation.csv")


@st.cache_data(ttl=600)
def load_prices() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "prix_maroc_faostat.csv")


@st.cache_data(ttl=600)
def load_daily() -> pd.DataFrame:
    p = ROOT / "data" / "prix_actuels.csv"
    return pd.read_csv(p, parse_dates=["date"]) if p.exists() else pd.DataFrame()


st.title("📈 Morocco Inflation Tracker")
st.caption(
    "Notre indice d'inflation **alimentaire indépendant** (panier de 21 produits "
    "de base) vs l'**inflation alimentaire officielle** du Maroc. "
    "Inspiré du Billion Prices Project du MIT."
)

idx = load_index()

# ---- headline metrics -------------------------------------------------------
both = idx.dropna(subset=["indice_nous", "cpi_food_officiel"])
if not both.empty:
    first, last = both.iloc[0], both.iloc[-1]
    infl_nous = (last["indice_nous"] / first["indice_nous"] - 1) * 100
    infl_food = (last["cpi_food_officiel"] / first["cpi_food_officiel"] - 1) * 100
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Notre inflation alimentaire ({int(first['annee'])}→{int(last['annee'])})",
              f"{infl_nous:+.0f}%")
    c2.metric("Inflation alimentaire officielle", f"{infl_food:+.0f}%")
    c3.metric("Écart résiduel", f"{infl_nous - infl_food:+.0f} pts",
              help="Reste surtout dû aux prix producteurs (plus volatils que le détail)")

# ---- index levels -----------------------------------------------------------
fig = go.Figure()
fig.add_trace(go.Scatter(x=idx["annee"], y=idx["indice_nous"], name="Notre indice (brut)",
                         mode="lines", line=dict(color=RAW, width=1.5, dash="dot")))
fig.add_trace(go.Scatter(x=idx["annee"], y=idx["indice_nous_lisse"],
                         name="Notre indice (lissé ≈ détail)",
                         mode="lines+markers", line=dict(color=OURS, width=2.8)))
fig.add_trace(go.Scatter(x=idx["annee"], y=idx["cpi_food_officiel"],
                         name="Inflation alimentaire officielle",
                         mode="lines+markers", line=dict(color=FOOD, width=2.5, dash="dash")))
fig.add_trace(go.Scatter(x=idx["annee"], y=idx["cpi_general_officiel"],
                         name="Inflation générale officielle (tous produits)",
                         mode="lines", line=dict(color=GEN, width=1.5)))
fig.update_layout(height=440, hovermode="x unified",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                  margin=dict(l=10, r=10, t=30, b=10),
                  yaxis_title="Indice (base 2010 = 100)")
st.plotly_chart(fig, use_container_width=True)

# ---- annual inflation rates -------------------------------------------------
st.subheader("Taux d'inflation annuel (%) — notre panier vs alimentaire officiel")
bar = go.Figure()
bar.add_trace(go.Bar(x=idx["annee"], y=idx["inflation_nous_%"], name="Notre panier",
                     marker_color=OURS))
bar.add_trace(go.Bar(x=idx["annee"], y=idx["inflation_food_off_%"], name="Alimentaire officiel",
                     marker_color=FOOD))
bar.update_layout(height=320, barmode="group",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                  margin=dict(l=10, r=10, t=10, b=10), yaxis_title="%")
st.plotly_chart(bar, use_container_width=True)

# ---- recent daily prices ----------------------------------------------------
daily = load_daily()
if not daily.empty:
    st.subheader("Prix de détail relevés récemment (scraping quotidien)")
    st.caption("Prix réels ajoutés chaque jour depuis Aswak Assalam, avec leur source.")
    st.dataframe(daily.sort_values("date").tail(60), use_container_width=True, hide_index=True)

# ---- per-product changes ----------------------------------------------------
st.subheader("Variation de prix par produit (base FAOSTAT)")
prices = load_prices()
piv = prices.pivot_table(index="produit", columns="annee", values="prix_mad_par_kg", aggfunc="first")
if len(piv.columns):
    y0, y1 = min(piv.columns), max(piv.columns)
    tbl = pd.DataFrame({"Produit": piv.index,
                        f"{y0} (MAD/kg)": piv[y0].values,
                        f"{y1} (MAD/kg)": piv[y1].values})
    tbl["Variation %"] = ((piv[y1].values / piv[y0].values - 1) * 100).round(0)
    st.dataframe(tbl.dropna().sort_values("Variation %", ascending=False),
                 use_container_width=True, hide_index=True)

with st.expander("Méthodologie, corrections et sources"):
    st.markdown(
        """
**Indice** (base 2010 = 100) : moyenne géométrique (Jevons) des prix par
catégorie, puis moyenne pondérée (Laspeyres) entre catégories, avec des poids
de consommation alimentaire (céréales 28%, viandes 22%, produits animaux 14%,
légumes 16%, fruits 12%, légumineuses 8%).

**Trois corrections pour une comparaison juste**
1. **Couverture** — on compare à l'**inflation alimentaire** officielle (et non
   l'indice tous produits), puisque notre panier est alimentaire.
2. **Producteur → détail** — les prix FAOSTAT sont des prix *à la production*,
   plus volatils que les prix en rayon ; on publie donc aussi une version
   **lissée** (moyenne mobile 3 ans) qui approche la « viscosité » du détail.
3. **Pondération** — poids alignés sur la structure de consommation alimentaire.

**Écart résiduel** — même corrigé, notre indice reste un peu au-dessus : les
prix **producteurs** ont plus augmenté que les prix **de détail** (marges,
produits transformés/importés dans le panier officiel). Le scraping quotidien
(prix de détail réels) corrige progressivement ce biais pour la période récente.

**Sources (vérifiables)**
- Prix producteurs : [FAOSTAT — Producer Prices](https://www.fao.org/faostat/fr/#data/PP) · `data/prix_maroc_faostat.csv`
- Inflation officielle : [FAOSTAT — Consumer Price Indices](https://www.fao.org/faostat/fr/#data/CP) · `data/official/cpi_maroc_faostat.csv`
- Prix de détail récents : Aswak Assalam · `data/prix_actuels.csv`
"""
    )
