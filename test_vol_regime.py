#!/usr/bin/env python3
"""H14 - Volatility-regime overlay (Phase-1 item #7).

Question: does Nifty's OWN volatility state add portfolio value beyond
the existing trend gate (Nifty>SMA200)?

Metric: Nifty ATR14/Close, ranked against its own trailing 252 sessions
(rolling percentile 0-100). Read at the LAST COMPLETED session before
the entry decision (no look-ahead).

PRE-REGISTERED variants (round thresholds fixed before looking at any
conditional stats):
  V0  baseline (trend gate only)            [published: 25.9-27.6% CAGR]
  V1  block NEW entries when vol>=90 pctl
  V2  block NEW entries when vol>=80 pctl
  V3  halve slots to 3 when vol>=80 pctl

Descriptive first: does high vol hurt WITHIN trend-open trades (if not,
V1-V3 can only destroy CAGR)? Then portfolio sim + Monte Carlo
head-to-head for any survivor.

ADOPTION GATE (declared now): DD improvement >= 5pts with CAGR drop
<= 2pts, AND bootstrap shows no CAGR tail destruction. Otherwise keep
the trend gate alone.
"""
import os

import numpy as np
import pandas as pd

from strategy_validation import CAPITAL
from test_fragility_mc import load_bundles, run_config
from test_portfolio_constraints import mc_head_to_head

HERE = os.path.dirname(os.path.abspath(__file__))


def nifty_vol_pctl():
    fp = os.path.join(HERE, "_price_cache", "NIFTY.csv")
    df = pd.read_csv(fp, parse_dates=["date"], index_col="date").sort_index()
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(),
                    (l - c.shift()).abs()], axis=1).max(axis=1)
    atrp = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean() / c
    return (atrp.rolling(252).rank(pct=True) * 100)


def vol_sim(trades, trend, vol_pctl, vol_block=None, slot_cut=None,
            return_taken=False):
    """constrained_sim clone with a volatility overlay."""
    vp = (vol_pctl.shift(1))  # last completed session's reading
    tr = trades.sort_values("entry_date")
    equity, curve, active = CAPITAL, [], []
    rets_taken = []
    skipped_vol = 0
    for _, t in tr.iterrows():
        d = t.entry_date
        if trend is not None and not bool(trend.asof(d)):
            continue
        v = float(vp.asof(d)) if np.isfinite(vp.asof(d)) else 50.0
        slots = 6
        if vol_block is not None and v >= vol_block:
            skipped_vol += 1
            continue
        if slot_cut is not None and v >= slot_cut[0]:
            slots = slot_cut[1]
        active = [a for a in active if a > d]
        if len(active) >= slots:
            continue
        active.append(t.exit_date)
        equity *= 1 + (t.ret_pct / 100) / 6
        curve.append((t.exit_date, equity))
        rets_taken.append(t.ret_pct)
    if not curve:
        out = ({}, None) if return_taken else {}
        return out
    ser = pd.Series({d: e for d, e in curve}).sort_index()
    yrs = (ser.index[-1] - ser.index[0]).days / 365.25
    out = {"cagr_pct": round(((ser.iloc[-1] / CAPITAL)
                              ** (1 / max(yrs, 0.25)) - 1) * 100, 1),
           "max_dd_pct": round(float((ser / ser.cummax() - 1).min()) * 100, 1),
           "taken": len(curve), "skip_vol": skipped_vol}
    if return_taken:
        return out, pd.DataFrame({"exit_date": [d for d, _ in curve],
                                  "ret_pct": rets_taken})
    return out


def main():
    bundles, rs_panel, trend = load_bundles()
    tr = run_config(bundles, rs_panel)
    r90 = tr[tr["rs90"]].copy()
    vp = nifty_vol_pctl()
    print(f"nifty vol pctl: median {vp.median():.0f}, "
          f"days >=80: {100*(vp>=80).mean():.0f}%, "
          f"days >=90: {100*(vp>=90).mean():.0f}%")

    # ---- descriptive: does vol matter WITHIN trend-open trades? ----
    r90 = r90.copy()
    r90["v"] = [float(vp.shift(1).asof(d)) for d in r90.entry_date]
    r90["gate"] = [bool(trend.asof(d)) for d in r90.entry_date]
    print("\n--- per-trade stats by vol bucket x regime gate ---")

    def pf(x):
        pos, neg = x[x > 0].sum(), abs(x[x <= 0].sum())
        return round(pos / neg, 2) if neg > 0 else float("nan")

    for g_lbl, g in [("GATE OPEN ", True), ("gate shut", False)]:
        seg = r90[r90.gate == g]
        for b_lbl, lo, hi in [("v<50     ", 0, 50), ("50-79    ", 50, 80),
                              ("v>=80    ", 80, 101)]:
            s = seg[(seg.v >= lo) & (seg.v < hi)]
            if len(s) == 0:
                print(f"{g_lbl} {b_lbl} n=0")
                continue
            print(f"{g_lbl} {b_lbl} n={len(s):>4} win={100*(s.ret_pct>0).mean():>4.0f}% "
                  f"avg={s.ret_pct.mean():>+6.2f}% PF={pf(s.ret_pct):>5}")

    # ---- portfolio overlays ----
    variants = [
        ("V0 baseline", {}),
        ("V1 skip v>=90", dict(vol_block=90)),
        ("V2 skip v>=80", dict(vol_block=80)),
        ("V3 slots->3 v>=80", dict(slot_cut=(80, 3))),
    ]
    print("\n" + "=" * 78)
    print("H14 VOLATILITY OVERLAY on RS>=90 book")
    print("=" * 78)
    seqs, taken_seqs = {}, {}
    for label, kw in variants:
        r, tk = vol_sim(r90, trend, vp, return_taken=True, **kw)
        tag = label.split()[0]
        seqs[tag], taken_seqs[tag] = r, tk
        print(f"{label:<22} CAGR={r['cagr_pct']:>5}% DD={r['max_dd_pct']:>6}% "
              f"taken={r['taken']:>4} skip_vol={r['skip_vol']:>3}")

    base = seqs["V0"]
    survivors = []
    for tag in ("V1", "V2", "V3"):
        r = seqs[tag]
        dd_gain = r["max_dd_pct"] - base["max_dd_pct"]   # +ve = shallower DD
        cagr_cost = base["cagr_pct"] - r["cagr_pct"]
        ok_gate = dd_gain >= 5 and cagr_cost <= 2
        if ok_gate:
            survivors.append(tag)
        print(f"{tag}: DD gain {dd_gain:+.1f}pts, CAGR cost {cagr_cost:+.1f}pts "
              f"-> {'PASS' if ok_gate else 'fail'}")

    if survivors:
        best = min(survivors, key=lambda t: taken_seqs[t].shape[0])
        print(f"\nMC head-to-head: V0 vs {best} "
              f"({dict(v1='skip v>=90', v2='skip v>=80', v3='slots->3 v>=80')[best.lower()]})")
        mc_head_to_head(taken_seqs["V0"], taken_seqs[best],
                        label_a="V0", label_b=best)


if __name__ == "__main__":
    main()
