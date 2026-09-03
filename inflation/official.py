"""Load the official HCP consumer price index for comparison.

The HCP publishes a monthly index. We keep it in a small CSV (month, index) and
rebase it onto the same 100-point base as our own index, so the two can be
plotted on one axis and the gap between them is meaningful.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_PATH = Path("data/official/hcp_ipc.csv")


def load_official(path: Path | str = DEFAULT_PATH) -> pd.DataFrame:
    """Return the official CPI as columns: month (datetime), index (float)."""
    df = pd.read_csv(path, parse_dates=["month"])
    return df.sort_values("month").reset_index(drop=True)


def rebase(
    df: pd.DataFrame, base_value: float = 100.0, base_month: str | None = None
) -> pd.DataFrame:
    """Rescale the official index so it equals `base_value` at `base_month`.

    Defaults to the first available month. Adds a `rebased` column.
    """
    d = df.copy()
    if base_month is None:
        ref = d["index"].iloc[0]
    else:
        ref = d.loc[d["month"] == pd.Timestamp(base_month), "index"].iloc[0]
    d["rebased"] = d["index"] / ref * base_value
    return d
