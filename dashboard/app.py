"""Morocco Inflation Tracker — public dashboard.

Three views: (1) our DAILY chained index of ~350 consumer products scraped from
Aswak Assalam, (2) a long-run comparison of our food index vs the official
Morocco food CPI, and (3) a method validation on the USA. Reads only committed
CSVs, so it deploys cleanly on Streamlit Community Cloud.

    streamlit run dashboard/app.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = "#93c5fd"
OURS = "#2563eb"
FOOD = "#e07a3f"
GEN = "#9ca3af"

# retail category -> CPI division (mirrors build_daily_index.DIVISION; housing
# is deliberately absent — it is tracked as a separate noisy series)
DIVISION = {
    "patisserie": "Alimentation", "boulangerie": "Alimentation",
    "fruits-legumes": "Alimentation", "boucherie-volaille": "Alimentation",
    "charcuterie-traiteur": "Alimentation", "cremerie": "Alimentation",
    "epicerie": "Alimentation", "biscuiterie-confiserie": "Alimentation",
    "boissons": "Alimentation",
    "beaute-hygiene": "Hygiène & entretien", "entretien": "Hygiène & entretien",
}

st.set_page_config(page_title="Morocco Inflation Tracker", page_icon="📈", layout="wide")


def _csv(name: str, **kw) -> pd.DataFrame:
    p = ROOT / "data" / name
    return pd.read_csv(p, **kw) if p.exists() else pd.DataFrame()


@st.cache_data(ttl=600)
def load_index() -> pd.DataFrame:
    return _csv("indice_inflation.csv")


@st.cache_data(ttl=600)
def load_prices() -> pd.DataFrame:
    return _csv("prix_maroc_faostat.csv")


@st.cache_data(ttl=600)
def load_daily() -> pd.DataFrame:
    return _csv("prix_actuels.csv", parse_dates=["date"])


@st.cache_data(ttl=600)
def load_validation() -> pd.DataFrame:
    return _csv("validation_usa.csv")


@st.cache_data(ttl=600)
def load_daily_index() -> pd.DataFrame:
    return _csv("indice_quotidien.csv", parse_dates=["date"])


@st.cache_data(ttl=600)
def load_housing() -> pd.DataFrame:
    return _csv("serie_logement.csv", parse_dates=["date"])


@st.cache_data(ttl=600)
def _weights() -> dict:
    p = ROOT / "config" / "weights.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")).get("divisions", {}) if p.exists() else {}


def covered_legend(daily_prices: pd.DataFrame) -> str:
    """Legend generated FROM the YAML weights, restricted to the divisions we
    actually collect and renormalised — never announces uncovered divisions."""
    if daily_prices.empty:
        return ""
    divs = {DIVISION[c] for c in daily_prices["categorie"].unique() if c in DIVISION}
    w = _weights()
    present = {d: w.get(d, 0.0) for d in divs}
    total = sum(present.values()) or 1.0
    return " · ".join(f"**{d} {v / total * 100:.0f}%**"
                      for d, v in sorted(present.items(), key=lambda x: -x[1]))


st.title("📈 Morocco Inflation Tracker")
st.caption(
    "Un indice d'inflation **indépendant** pour le Maroc : un indice **quotidien** "
    "de ~350 produits scrapés, comparé à l'inflation officielle. "
    "Inspiré du Billion Prices Project du MIT."
)

# ---- DAILY index (headline: food + hygiene, the real observations) ----------
di = load_daily_index()
if not di.empty:
    st.subheader("🗓️ Indice quotidien — alimentation & hygiène (temps réel)")
    latest = di.iloc[-1]
    d1, d2, d3 = st.columns(3)
    d1.metric("Indice du jour", f"{latest['indice_quotidien']:.2f}",
              f"{latest['indice_quotidien'] - 100:+.2f}% vs départ")
    d2.metric("Produits suivis", int(latest["n_produits"]))
    d3.metric("Jours collectés", len(di))

    daily = load_daily()
    leg = covered_legend(daily)
    if leg:
        st.caption(f"Panier pondéré (poids HCP renormalisés sur les divisions **réellement "
                   f"couvertes**) : {leg}. Le loyer est suivi **à part** (proxy bruité, ci-dessous).")

    if len(di) >= 7:
        dfig = go.Figure()
        dfig.add_trace(go.Scatter(x=di["date"], y=di["indice_quotidien"],
                                  mode="lines+markers", line=dict(color=OURS, width=2.5)))
        dfig.update_layout(height=330, hovermode="x unified",
                           margin=dict(l=10, r=10, t=10, b=10),
                           yaxis_title="Indice (base 100 au départ)")
        st.plotly_chart(dfig, use_container_width=True)
    elif len(di) >= 2:
        # too few points for a line — it would falsely suggest a trend
        dfig = go.Figure()
        dfig.add_trace(go.Scatter(x=di["date"], y=di["indice_quotidien"],
                                  mode="markers", marker=dict(color=OURS, size=12)))
        dfig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                           yaxis_title="Indice (base 100)")
        st.plotly_chart(dfig, use_container_width=True)
        st.caption(f"Seulement **{len(di)} jours** collectés — on affiche des points, pas une "
                   "courbe (une ligne suggérerait une fausse tendance). Série démarrée en "
                   "sept. 2026, +1 point/jour.")
    else:
        st.info(f"📈 Série démarrée (base 100, {int(latest['n_produits'])} produits). "
                "Elle s'enrichit d'un point chaque jour.")

    # price-change frequency — a real BPP-literature metric
    if len(di) >= 2 and not daily.empty:
        piv = (daily[daily["categorie"] != "logement"]
               .pivot_table(index="product_id", columns="date", values="prix", aggfunc="median"))
        if piv.shape[1] >= 2:
            last2 = piv.iloc[:, -2:].dropna()
            if len(last2):
                changed = (last2.iloc[:, 0] != last2.iloc[:, 1]).mean() * 100
                st.caption(f"📊 **{changed:.0f}% des prix ont changé** entre les deux derniers "
                           "jours. Les prix de détail sont rigides (Cavallo : ~1 changement "
                           "toutes les 2–3 semaines) — d'où un indice quotidien peu volatil.")

    # housing shown separately, honestly labelled
    hz = load_housing()
    if not hz.empty:
        st.caption(f"🏠 **Loyer (Mubawab)** — proxy d'annonces **très bruité, hors indice** : "
                   f"dernier {hz['loyer_dh_m2'].iloc[-1]:.0f} DH/m²/mois. Exclu du headline car "
                   "il bouge surtout selon les annonces listées, pas les vrais loyers "
                   "(les IPC relèvent les loyers trimestriellement).")
    st.divider()

idx = load_index()

# ---- long-run comparison (context) -----------------------------------------
st.subheader("📅 Comparaison longue durée (contexte annuel)")

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
                         name="Notre indice (lissé, lisibilité)",
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

# ---- gap analysis (the raison d'être) --------------------------------------
st.subheader("Écart cumulé — notre indice vs officiel")
g = idx.dropna(subset=["indice_nous", "cpi_food_officiel"]).copy()
g["ecart"] = (g["indice_nous"] - g["cpi_food_officiel"]).round(1)
gfig = go.Figure()
gfig.add_trace(go.Scatter(x=g["annee"], y=g["ecart"], fill="tozeroy",
                          mode="lines+markers", line=dict(color="#dc2626", width=2),
                          name="Écart (points d'indice)"))
gfig.add_hline(y=0, line=dict(color="#6b7280", width=1))
gfig.update_layout(height=280, hovermode="x unified",
                   margin=dict(l=10, r=10, t=10, b=10),
                   yaxis_title="Écart (points, base 2010)")
st.plotly_chart(gfig, use_container_width=True)
st.caption(
    "Au-dessus de 0 : notre panier alimentaire signale **plus** d'inflation que "
    "l'indice officiel. L'écart se creuse à partir de 2020 (prix producteurs très "
    "volatils lors de la sécheresse et de la flambée mondiale)."
)

# ---- method validation on the USA (honest metrics) --------------------------
val = load_validation()
if not val.empty:
    st.subheader("🇺🇸 Validation de la méthode sur les USA")
    v = val.sort_values("annee").copy()
    v["yoy_n"] = v["indice_nous_usa"].pct_change() * 100
    v["yoy_o"] = v["cpi_food_usa"].pct_change() * 100
    yv = v.dropna(subset=["yoy_n", "yoy_o"])
    yoy_corr = yv["yoy_n"].corr(yv["yoy_o"])
    mae = (yv["yoy_n"] - yv["yoy_o"]).abs().mean()
    cum_n = (v["indice_nous_usa"].iloc[-1] / v["indice_nous_usa"].iloc[0] - 1) * 100
    cum_o = (v["cpi_food_usa"].iloc[-1] / v["cpi_food_usa"].iloc[0] - 1) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Corrélation (taux annuels)", f"{yoy_corr:.2f}",
              help="Le test honnête : sur les variations annuelles (stationnaires), pas les niveaux")
    c2.metric("Erreur moyenne (MAE)", f"{mae:.1f} pts")
    c3.metric("Inflation cumulée", f"+{cum_n:.0f}%", f"officiel +{cum_o:.0f}%", delta_color="off")
    st.caption(
        "⚠️ Corréler les **niveaux** de deux séries qui montent donne toujours ~0,99 "
        "(piège de Granger–Newbold : même une tendance bidon `exp(0,03·t)` atteint 0,99). "
        "Le vrai test est sur les **taux annuels** (affichés ci-dessus) avec 13 produits "
        "sur 46 ans — un résultat honnête. L'écart de niveau cumulé "
        "vient d'un panier plus étroit que le CPI officiel."
    )
    vfig = go.Figure()
    vfig.add_trace(go.Scatter(x=yv["annee"], y=yv["yoy_n"], name="Notre méthode",
                              mode="lines", line=dict(color=OURS, width=2.2)))
    vfig.add_trace(go.Scatter(x=yv["annee"], y=yv["yoy_o"], name="CPI alimentaire officiel US",
                              mode="lines", line=dict(color=FOOD, width=2, dash="dash")))
    vfig.update_layout(height=320, hovermode="x unified",
                       legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                       margin=dict(l=10, r=10, t=10, b=10),
                       yaxis_title="Inflation annuelle (%)")
    st.plotly_chart(vfig, use_container_width=True)
    st.caption(
        "Là où de vrais prix de détail existent (USA), la méthode **suit** l'inflation "
        "officielle année après année. Au Maroc, il manque cette donnée de détail — "
        "c'est un problème de données, pas de méthode."
    )

# ---- today's scraped prices (compact) ---------------------------------------
daily = load_daily()
if not daily.empty:
    st.subheader("Derniers prix relevés (Aswak Assalam)")
    last_day = daily["date"].max()
    view = (daily[(daily["date"] == last_day) & (daily["categorie"] != "logement")]
            .assign(Jour=last_day.date().isoformat())
            [["Jour", "produit", "categorie", "prix"]]
            .rename(columns={"produit": "Produit", "categorie": "Catégorie", "prix": "Prix (DH)"})
            .sort_values("Catégorie"))
    st.caption(f"{len(view)} produits relevés le {last_day.date().isoformat()}. "
               "Source de chaque prix : `data/prix_actuels.csv` (colonne source_url).")
    st.dataframe(view, use_container_width=True, hide_index=True, height=280)

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

# ---- what drives inflation, by category -------------------------------------
st.subheader("Ce qui tire l'inflation, par catégorie")
if len(piv.columns):
    y0, y1 = min(piv.columns), max(piv.columns)
    prices2 = prices[prices["annee"].isin([y0, y1])]
    contrib = []
    for cat, gc in prices2.groupby("categorie"):
        w = gc.pivot_table(index="produit", columns="annee", values="prix_mad_par_kg", aggfunc="first").dropna()
        if w.empty:
            continue
        change = float(np.exp(np.log(w[y1] / w[y0]).mean()) - 1) * 100
        contrib.append((cat, round(change, 1)))
    cdf = pd.DataFrame(contrib, columns=["Catégorie", "Variation %"]).sort_values("Variation %")
    cbar = go.Figure(go.Bar(x=cdf["Variation %"], y=cdf["Catégorie"], orientation="h",
                            marker_color=["#dc2626" if v > 0 else "#2563eb" for v in cdf["Variation %"]]))
    cbar.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                       xaxis_title=f"Variation du prix moyen {y0}→{y1} (%)")
    st.plotly_chart(cbar, use_container_width=True)

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
   plus volatils que les prix en rayon. La version **lissée** (moyenne mobile
   3 ans) est un **lissage de lisibilité** — elle ne convertit *pas* un prix
   producteur en prix de détail (il faudrait modéliser marge + délai).
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
