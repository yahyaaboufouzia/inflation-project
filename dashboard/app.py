"""Morocco Inflation Tracker — public dashboard.

Compares OUR inflation index (a basket of 21 Moroccan food staples, built from
FAOSTAT producer prices and extended with daily scraped prices) against the
official Morocco CPI (World Bank). Reads only committed CSVs, so it deploys
cleanly on Streamlit Community Cloud.

    streamlit run dashboard/app.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
OURS = "#2563eb"
OFF = "#e07a3f"

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
    "Notre indice d'inflation **indépendant** (panier de 21 produits de base "
    "marocains) vs l'**inflation officielle** (CPI, Banque mondiale). "
    "Inspiré du Billion Prices Project du MIT."
)

idx = load_index()
idx = idx.dropna(subset=["indice_nous", "indice_officiel"], how="all")

# ---- headline metrics -------------------------------------------------------
both = idx.dropna(subset=["indice_nous", "indice_officiel"])
if not both.empty:
    first, last = both.iloc[0], both.iloc[-1]
    infl_nous = (last["indice_nous"] / first["indice_nous"] - 1) * 100
    infl_off = (last["indice_officiel"] / first["indice_officiel"] - 1) * 100
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Notre inflation cumulée ({int(first['annee'])}→{int(last['annee'])})",
              f"{infl_nous:+.0f}%")
    c2.metric("Inflation officielle cumulée", f"{infl_off:+.0f}%")
    c3.metric("Écart", f"{infl_nous - infl_off:+.0f} pts",
              help="Écart entre notre panier alimentaire et l'indice officiel tous produits")
    st.caption(f"Base 100 = {int(first['annee']) if first['annee']<=2010 else 2010}. "
               "Notre indice = 21 staples ; officiel = tous produits.")

# ---- index levels -----------------------------------------------------------
fig = go.Figure()
fig.add_trace(go.Scatter(x=idx["annee"], y=idx["indice_nous"],
                         name="Notre indice (panier alimentaire)",
                         mode="lines+markers", line=dict(color=OURS, width=2.5)))
fig.add_trace(go.Scatter(x=idx["annee"], y=idx["indice_officiel"],
                         name="Inflation officielle (CPI, Banque mondiale)",
                         mode="lines+markers", line=dict(color=OFF, width=2.5, dash="dot")))
fig.update_layout(height=430, hovermode="x unified",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                  margin=dict(l=10, r=10, t=30, b=10),
                  yaxis_title="Indice (base 2010 = 100)")
st.plotly_chart(fig, use_container_width=True)

# ---- annual inflation rates -------------------------------------------------
st.subheader("Taux d'inflation annuel (%)")
bar = go.Figure()
bar.add_trace(go.Bar(x=idx["annee"], y=idx["inflation_nous_%"],
                     name="Notre panier", marker_color=OURS))
bar.add_trace(go.Bar(x=idx["annee"], y=idx["inflation_officiel_%"],
                     name="Officiel", marker_color=OFF))
bar.update_layout(height=320, barmode="group",
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                  margin=dict(l=10, r=10, t=10, b=10), yaxis_title="%")
st.plotly_chart(bar, use_container_width=True)

# ---- recent daily prices (if collected) -------------------------------------
daily = load_daily()
if not daily.empty:
    st.subheader("Prix relevés récemment (scraping quotidien)")
    st.caption("Prix de détail réels ajoutés chaque jour depuis Aswak Assalam.")
    st.dataframe(daily.sort_values("date").tail(60), use_container_width=True, hide_index=True)

# ---- per-product changes ----------------------------------------------------
st.subheader("Variation de prix par produit (base FAOSTAT)")
prices = load_prices()
piv = prices.pivot_table(index="produit", columns="annee", values="prix_mad_par_kg", aggfunc="first")
yrs = [c for c in piv.columns]
if yrs:
    y0, y1 = min(yrs), max(yrs)
    tbl = pd.DataFrame({
        "Produit": piv.index,
        f"{y0} (MAD/kg)": piv[y0].values,
        f"{y1} (MAD/kg)": piv[y1].values,
    })
    tbl["Variation %"] = ((piv[y1].values / piv[y0].values - 1) * 100).round(0)
    tbl = tbl.dropna().sort_values("Variation %", ascending=False)
    st.dataframe(tbl, use_container_width=True, hide_index=True)

with st.expander("Méthodologie, sources et limites"):
    st.markdown(
        """
**Notre indice** — panier de 21 produits de base (céréales, légumes, fruits,
légumineuses, viandes, lait, œufs). Moyenne géométrique (Jevons) par catégorie,
puis moyenne pondérée (Laspeyres) entre catégories. Base 2010 = 100.

**Sources (vérifiables)**
- Prix des produits : **FAOSTAT — Producer Prices (Maroc)**, `data/prix_maroc_faostat.csv`
  → [faostat](https://www.fao.org/faostat/fr/#data/PP)
- Inflation officielle : **Banque mondiale — FP.CPI.TOTL**
  → [data.worldbank.org](https://data.worldbank.org/indicator/FP.CPI.TOTL?locations=MA)

**Limites (à assumer)**
- FAOSTAT donne des **prix à la production** (annuels), pas des prix en rayon :
  ils sont plus volatils et notre indice ne couvre que l'**alimentaire**, alors
  que le CPI officiel couvre **tous les produits** (dont le logement, stable).
  D'où un écart attendu : l'alimentaire a bien plus augmenté que l'indice global.
- Le scraping quotidien (Aswak Assalam) ajoute des **prix de détail réels** au
  fil du temps pour affiner la partie récente.
"""
    )
