#!/usr/bin/env python3
"""Validate the PULLBACK system on the Nifty-500 SANDBOX cache.

Reuses the exact engine that reproduced the published anchor
(n=28630 PF=1.34 avg=+1.02% gated CAGR=13.7% on the top-150 universe),
only the data directory differs (_price_cache_n500/).
Read-only: touches nothing the live scanner uses.
"""
import glob
import os

import numpy as np
import pandas as pd

import strategy_validation as sv
from test_fragility_mc import brief, run_config

HERE = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(HERE, "_price_cache_n500")

# Published top-150 anchors for side-by-side comparison
N150 = {"full": dict(n=28630, pf=1.34, avg=1.02, cagr=13.7),
        "rs90": dict(n=1294, pf=1.72, cagr=27.5)}


def load_data_sandbox():
    data = {}
    for fp in sorted(glob.glob(os.path.join(SB, "*.csv"))):
        sym = os.path.splitext(os.path.basename(fp))[0]
        if sym == "NIFTY" or sym.startswith("sectors"):
            continue
        try:
            df = pd.read_csv(fp, parse_dates=["date"], index_col="date")
        except Exception:
            continue
        if len(df) < 300:
            continue
        data[sym] = sv.add_indicators(df)
    nifty = pd.read_csv(os.path.join(SB, "NIFTY.csv"),
                        parse_dates=["date"], index_col="date")
    print(f"sandbox: loaded {len(data)} tradable series "
          f"({nifty.index[-1].date()} latest)")
    return data, nifty


def load_bundles():
    data, nifty = load_data_sandbox()
    trend = (nifty["Close"] > nifty["Close"].rolling(200).mean()).fillna(False)
    trend.index = trend.index.tz_localize(None)
    bundles = []
    for tk, df in data.items():
        sigs = sv.signals(df)["pullback"]
        if len(sigs) == 0:
            continue
        idx = np.array([df.index.searchsorted(d) for d in sigs])
        bundles.append((tk, df["Open"].to_numpy(float),
                        df["High"].to_numpy(float), df["Low"].to_numpy(float),
                        df["ATR"].to_numpy(float), df.index, idx))
    px = pd.DataFrame({tk: d["Close"] for tk, d in data.items()})
    rs_panel = ((px / px.shift(252) - 1).rank(axis=1, pct=True) * 99)
    return bundles, rs_panel, trend


def main():
    bundles, rs_panel, trend = load_bundles()
    print(f"bundles: {len(bundles)} symbols with >=1 pullback signal")

    tr = run_config(bundles, rs_panel)          # BASE buf.25 lb5 2R ts20
    tr["rs_val"] = [
        float(rs_panel.at[e, tk]) if tk in rs_panel.columns
        and e in rs_panel.index else np.nan
        for tk, e in zip(tr["ticker"], tr["entry_date"])]

    # cost stress: +20 bps round-trip (small-cap slippage proxy)
    tr_hi = tr.copy()
    tr_hi["ret_pct"] = (tr_hi["ret_pct"] - 0.2).round(2)

    s = sv.stats(tr)
    print("\n=== NIFTY-500 SANDBOX vs TOP-150 PUBLISHED ===")
    brief(tr, trend, f"N500 full (was n={N150['full']['n']} PF={N150['full']['pf']} "
                     f"CAGR={N150['full']['cagr']}%)")
    r90 = tr[tr["rs90"]]
    brief(r90, trend, f"N500 RS>=90 (was n={N150['rs90']['n']} PF={N150['rs90']['pf']} "
                      f"CAGR={N150['rs90']['cagr']}%)")
    brief(tr[tr["rs_val"] >= 95], trend, "N500 RS>=95:")
    brief(tr[tr["rs_val"] >= 98], trend, "N500 RS>=98:")
    brief(r90[r90["rs_val"] >= 97], trend, "N500 RS>=97:")
    lo = tr[~tr["rs90"]]
    brief(lo, trend, "N500 RS<90:")
    print("--- cost stress (+20 bps) ---")
    brief(tr_hi[tr_hi["rs90"]], trend, "RS>=90:")
    brief(tr_hi[tr_hi["rs_val"] >= 95], trend, "RS>=95:")

    # era stability for the RS90 book
    for a, b in [(2010, 2017), (2018, 2026)]:
        seg = r90[(r90["entry_date"] >= f"{a}-01-01")
                  & (r90["entry_date"] <= f"{b}-12-31")]
        brief(seg, trend, f"RS>=90 {a}-{b}:")

    # small-cap liquidity proxy: bottom quartile by price*volume turnover
    med = r90.copy()
    if len(med):
        med["yr"] = pd.DatetimeIndex(med["entry_date"]).year
        print("\ntrades/year (RS>=90):")
        print(med.groupby("yr").size().to_string())

    out = os.path.join(HERE, "_n500_pullback_trades.csv")
    tr.to_csv(out, index=False)
    print(f"\ntrade list -> {out}")


if __name__ == "__main__":
    main()
