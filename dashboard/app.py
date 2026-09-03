"""Streamlit dashboard: our daily index vs the official monthly CPI.

Run from the repo root:

    streamlit run dashboard/app.py

Deployable as-is on Streamlit Community Cloud to get a public link.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from inflation import official  # noqa: E402
from inflation.index import top_movers  # noqa: E402
from inflation.storage import repository as repo  # noqa: E402

st.set_page_config(page_title="Morocco Inflation Tracker", page_icon="📈", layout="wide")

INK = "#1f2a44"
OURS = "#2563eb"
HCP = "#e07a3f"


@st.cache_data(ttl=600)
def load_index() -> pd.DataFrame:
    engine = repo.get_engine(ROOT / "data" / "prices.db")
    return repo.index_df(engine)


@st.cache_data(ttl=600)
def load_observations() -> pd.DataFrame:
    engine = repo.get_engine(ROOT / "data" / "prices.db")
    return repo.observations_df(engine)


@st.cache_data(ttl=600)
def load_official() -> pd.DataFrame:
    path = ROOT / "data" / "official" / "hcp_ipc.csv"
    return official.load_official(path) if path.exists() else pd.DataFrame()


st.title("📈 Morocco Inflation Tracker")
st.caption(
    "An independent, daily price index for Morocco, built from online prices — "
    "compared against the official HCP consumer price index. "
    "Inspired by MIT's Billion Prices Project."
)

index = load_index()
obs = load_observations()
off = load_official()

if index.empty:
    st.warning(
        "No index data yet. Seed the demo history first:\n\n"
        "```bash\npython scripts/seed_demo.py\n```"
    )
    st.stop()

index["day"] = pd.to_datetime(index["day"])
base_day = index["day"].min()

# rebase the official CPI onto our 100 base, at the month of our base day
official_line = pd.DataFrame()
if not off.empty:
    base_month = base_day.to_period("M").to_timestamp()
    if (off["month"] == base_month).any():
        official_line = official.rebase(off, 100.0, base_month.strftime("%Y-%m-%d"))
    else:
        official_line = official.rebase(off, 100.0)
    official_line = official_line[official_line["month"] >= base_day - pd.Timedelta(days=31)]

# ---- headline metrics -------------------------------------------------------
latest = index.iloc[-1]
our_change = latest["value"] - 100.0

col1, col2, col3 = st.columns(3)
col1.metric("Our index (latest)", f"{latest['value']:.1f}", f"{our_change:+.2f}% vs base")
if not official_line.empty:
    off_change = official_line["rebased"].iloc[-1] - 100.0
    col2.metric("Official HCP (rebased)", f"{official_line['rebased'].iloc[-1]:.1f}",
                f"{off_change:+.2f}% vs base")
    col3.metric("Gap (ours − official)", f"{our_change - off_change:+.2f} pts")
col1.caption(f"Base = 100 on {base_day:%d %b %Y} · {len(index)} days tracked")

# ---- the two curves ---------------------------------------------------------
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=index["day"], y=index["value"], name="Our daily index",
        mode="lines", line=dict(color=OURS, width=2.5),
    )
)
if not official_line.empty:
    fig.add_trace(
        go.Scatter(
            x=official_line["month"], y=official_line["rebased"],
            name="Official HCP (monthly)", mode="lines+markers",
            line=dict(color=HCP, width=2, dash="dot"), marker=dict(size=7),
        )
    )
fig.update_layout(
    height=460, hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    margin=dict(l=10, r=10, t=30, b=10),
    yaxis_title="Index (base 100)", xaxis_title=None,
)
st.plotly_chart(fig, use_container_width=True)

# ---- top movers -------------------------------------------------------------
st.subheader("What's driving the index")
movers = top_movers(obs, base_day=base_day.date(), n=8)
if not movers.empty:
    movers = movers.rename(
        columns={
            "product_name": "Product",
            "p0": "Base price (MAD)",
            "latest": "Latest price (MAD)",
            "change_pct": "Change %",
        }
    )
    st.dataframe(
        movers.style.format(
            {"Base price (MAD)": "{:.2f}", "Latest price (MAD)": "{:.2f}", "Change %": "{:+.1f}%"}
        ),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Why might the two curves diverge?"):
    st.markdown(
        """
- **Different basket.** We track online products; the HCP tracks a fixed
  in-store basket. The overlap is partial.
- **Online vs in-store prices.** Web prices move faster and promotions are
  more frequent online.
- **Frequency.** Ours is daily and reacts immediately; the official index is
  monthly and smoothed.
- **Coverage.** We cover a handful of cities' online offers, not the whole country.

The goal is not to be *right against* the HCP — it is to **explain the gap**.
"""
    )
