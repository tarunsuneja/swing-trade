#!/usr/bin/env python3
"""Live helper for the adopted H10 portfolio rule:

    SKIP a new entry if its trailing-120d return correlation with ANY
    open position >= 0.80 (doc s23).

Usage from code:
    from corr_guard import max_corr_vs_open
    mc = max_corr_vs_open("BEL", ["HAL", "POWERINDIA"])
    if mc is not None and mc >= 0.80: skip

CLI:   py corr_guard.py BEL HAL POWERINDIA
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "_price_cache")
WINDOW = 120
THRESHOLD = 0.80


def _close(sym: str) -> pd.Series | None:
    fp = os.path.join(CACHE, f"{sym}.csv")
    if not os.path.exists(fp):
        return None
    try:
        df = pd.read_csv(fp, usecols=["date", "Close"],
                         parse_dates=["date"], index_col="date")
        return df["Close"]
    except Exception:
        return None


def max_corr_vs_open(candidate: str, open_tickers: list[str],
                     asof=None) -> float | None:
    """Highest correlation between candidate and open positions.

    Returns None if no usable comparison exists (<60 common sessions).
    """
    c = _close(candidate)
    if c is None or not open_tickers:
        return None
    px = pd.concat([c] + [s for s in (_close(t) for t in open_tickers)
                          if s is not None], axis=1).dropna()
    if asof is not None:
        px = px.loc[px.index <= pd.Timestamp(asof)]
    px = px.tail(WINDOW)
    if len(px) < 60:
        return None
    rets = px.pct_change().dropna()
    corrs = rets.corr().iloc[1:, 0]
    corrs = corrs[np.isfinite(corrs)]
    return round(float(corrs.max()), 2) if len(corrs) else None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    cand, opens = sys.argv[1], sys.argv[2:]
    mc = max_corr_vs_open(cand, opens)
    if mc is None:
        print(f"{cand}: no comparable history vs {opens}")
    else:
        verdict = "SKIP - too correlated" if mc >= THRESHOLD else "ok"
        print(f"{cand} vs {opens}: max corr {mc:.2f} -> {verdict}")
