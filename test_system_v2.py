#!/usr/bin/env python3
"""SYSTEM v2 - consolidated validation of ALL adopted overlays stacked.

Individually validated pieces being combined:
  - RS>=90 book + regime gate            (published baseline s16/s18)
  - correlation guard: skip candidate with 120d corr >=0.80 vs ANY open
    position                             (H10, s23)
  - volatility hold: no NEW entries when Nifty ATR% >= its trailing-252
    90th percentile                      (H14, s27)
  (H12 freshness + official-sector TIER2 are live-scanner layers; the
   backtest already enters at trigger+1, so nothing extra to simulate.)

PRE-REGISTERED adoption bar for v2 (declared before running):
  DD <= -30% AND CAGR within 2pts of baseline, AND Monte Carlo shows
  shallower/equal drawdown tails with NO terminal-equity destruction.
"""
import numpy as np
import pandas as pd

from strategy_validation import CAPITAL
from test_fragility_mc import load_bundles, run_config
from test_portfolio_constraints import mc_head_to_head
from test_vol_regime import nifty_vol_pctl


def v2_sim(trades, trend, vp, rets, use_corr=False, use_vol=False,
           win=120, return_taken=False):
    vp_lag = vp.shift(1)
    tr = trades.sort_values("entry_date")
    equity, curve, active, rets_taken = CAPITAL, [], [], []
    sk_reg = sk_corr = sk_vol = 0
    for _, t in tr.iterrows():
        d = t.entry_date
        if trend is not None and not bool(trend.asof(d)):
            sk_reg += 1
            continue
        active = [a for a in active if a["exit"] > d]
        if len(active) >= 6:
            continue
        if use_vol:
            v = float(vp_lag.asof(d))
            if np.isfinite(v) and v >= 90:
                sk_vol += 1
                continue
        if use_corr and len(active):
            hist = rets.loc[rets.index <= d].tail(win)
            if len(hist) >= 60:
                blocked = False
                for a in active:
                    cols = [t.ticker, a["tk"]]
                    if all(c in hist.columns for c in cols):
                        c = hist[cols].corr().iloc[0, 1]
                        if np.isfinite(c) and c >= 0.80:
                            blocked = True
                            break
                if blocked:
                    sk_corr += 1
                    continue
        active.append({"exit": t.exit_date, "tk": t.ticker})
        equity *= 1 + (t.ret_pct / 100) / 6
        curve.append((t.exit_date, equity))
        rets_taken.append(t.ret_pct)
    out = {}
    if curve:
        ser = pd.Series({d: e for d, e in curve}).sort_index()
        yrs = (ser.index[-1] - ser.index[0]).days / 365.25
        out = {"cagr_pct": round(((ser.iloc[-1] / CAPITAL)
                                  ** (1 / max(yrs, .25)) - 1) * 100, 1),
               "max_dd_pct": round(float((ser / ser.cummax() - 1).min()) * 100, 1),
               "taken": len(curve)}
    if return_taken:
        out = (out, pd.DataFrame({"exit_date": [d for d, _ in curve],
                                  "ret_pct": rets_taken}))
    return out


def main():
    bundles, rs_panel, trend = load_bundles()
    tr = run_config(bundles, rs_panel)
    r90 = tr[tr["rs90"]].copy()
    vp = nifty_vol_pctl()
    data, _ = __import__("strategy_validation").load_data()
    px = pd.DataFrame({tk: d["Close"] for tk, d in data.items()})
    rets = px.pct_change()

    variants = [
        ("V0 published baseline", {}),
        ("V1 corr-guard only", dict(use_corr=True)),
        ("V2 vol-hold only", dict(use_vol=True)),
        ("V3 SYSTEM v2 (both)", dict(use_corr=True, use_vol=True)),
    ]
    print("=" * 76)
    print("SYSTEM v2 CONSOLIDATED (RS>=90 book, regime-gated)")
    print("=" * 76)
    taken_seqs = {}
    rows_res = {}
    for label, kw in variants:
        r, tk = v2_sim(r90, trend, vp, rets, return_taken=True, **kw)
        tag = label.split()[0]
        taken_seqs[tag] = tk
        rows_res[tag] = r
        print(f"{label:<24} CAGR={r['cagr_pct']:>5}% DD={r['max_dd_pct']:>6}% "
              f"taken={r['taken']:>4}")

    b, v = rows_res["V0"], rows_res["V3"]
    dd_gain = v["max_dd_pct"] - b["max_dd_pct"]
    cagr_cost = b["cagr_pct"] - v["cagr_pct"]
    ok_bar = (v["max_dd_pct"] >= -30 and abs(cagr_cost) <= 2.0)
    print(f"\nv2 vs baseline: DD gain {dd_gain:+.1f}pts, "
          f"CAGR cost {cagr_cost:+.1f}pts -> "
          f"{'MEETS PRE-REGISTERED BAR' if ok_bar else 'MISSES BAR'}")

    # half-split robustness for v2
    mid = r90.entry_date.median()
    print("\nhalf-split (v2):")
    for lbl, sub in [("first half", r90[r90.entry_date <= mid]),
                     ("second  ", r90[r90.entry_date > mid])]:
        r = v2_sim(sub, trend, vp, rets, use_corr=True, use_vol=True)
        print(f"  {lbl}: CAGR={r.get('cagr_pct','?'):>5}% "
              f"DD={r.get('max_dd_pct','?'):>6}% taken={r.get('taken', 0)}")

    print("\nMonte Carlo head-to-head: V0 vs V3 (4,000 paths)")
    mc_head_to_head(taken_seqs["V0"], taken_seqs["V3"],
                    label_a="V0", label_b="v2", n_paths=4000)


if __name__ == "__main__":
    main()
