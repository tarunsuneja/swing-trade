#!/usr/bin/env python3
"""H9 - Entry gap/chase policy backtest (Phase 1.1).

Question: the engine enters unconditionally at next open. Do entry
filters improve results?
  - CHASE CAP : skip if next open > signal close * (1 + k * ATR14/close)
  - GAP-DN    : skip if next open < plan stop (fill would die instantly)

Baseline must reproduce the published anchor (n=28630 PF=1.34 avg=+1.02).
Secondary realism table: stop anchored to the PLAN level (signal bar)
instead of recomputed from actual fill - matches how resting SLs behave.
Read-only over the live cache.
"""
import numpy as np
import pandas as pd

from strategy_validation import stats
from test_fragility_mc import brief, load_bundles

COST = 0.0030


def sim_gap(o, h, l, atr, closes, dates, sig_i, tk,
            chase_k=None, gapdn=False, plan_anchor=False,
            stop_buf=0.25, stop_lb=5, tgt_r=2.0, tstop=20):
    rows = []
    n = len(dates)
    for i in sig_i:
        if i + 1 >= n:
            continue
        entry = o[i + 1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        ref = closes[i]
        lo = l[max(0, i - stop_lb + 1):i + 1].min()
        plan_stop = min(lo, ref - 2 * a) - stop_buf * a

        # --- entry policies ---
        if chase_k is not None and entry > ref * (1 + chase_k * a / ref):
            continue
        if gapdn and entry < plan_stop:
            continue

        # --- stop anchoring ---
        if plan_anchor:
            stop = plan_stop
            if entry <= stop:          # filled at/below plan stop -> out day 1
                net = (stop / entry - 1) - COST
                risk = (ref - plan_stop) / ref
                rows.append({"ticker": tk, "entry_date": dates[i + 1],
                             "exit_date": dates[i + 1],
                             "ret_pct": round(net * 100, 2),
                             "r": round(net / risk, 2) if risk > 0 else np.nan,
                             "hold_days": 1})
                continue
        else:
            stop = min(lo, entry - 2 * a) - stop_buf * a
        tgt = entry + tgt_r * (entry - stop)
        exit_px = exit_i = None
        for j in range(i + 1, min(i + 1 + tstop, n)):
            if l[j] <= stop:
                exit_px, exit_i = stop, j
                break
            if h[j] >= tgt:
                exit_px, exit_i = tgt, j
                break
        if exit_px is None:
            j = min(i + tstop, n - 1)
            exit_px, exit_i = o[j], j
        net = (exit_px / entry - 1) - COST
        risk = (entry - stop) / entry
        rows.append({"ticker": tk, "entry_date": dates[i + 1],
                     "exit_date": dates[exit_i],
                     "ret_pct": round(net * 100, 2),
                     "r": round(net / risk, 2) if risk > 0 else np.nan,
                     "hold_days": int(exit_i - (i + 1)) + 1})
    return rows


_closes = {}


def run(bundles, rs_panel, **kw):
    rows = []
    for tk, o, h, l, atr, dates, idx in bundles:
        rows += sim_gap(o, h, l, atr, _closes[tk], dates, idx, tk, **kw)
    tr = pd.DataFrame(rows)
    tr["rs90"] = [
        bool(tk in rs_panel.columns and e in rs_panel.index
             and rs_panel.at[e, tk] >= 90)
        for tk, e in zip(tr["ticker"], tr["entry_date"])]
    return tr


def main():
    bundles, rs_panel, trend = load_bundles()

    from strategy_validation import load_data
    data, _ = load_data()
    keep = {b[0] for b in bundles}
    _closes.update({tk: d["Close"].to_numpy(float)
                    for tk, d in data.items() if tk in keep})

    configs = [
        ("V0 baseline (no filter)", {}),
        ("chase<=0.25 ATR", dict(chase_k=0.25)),
        ("chase<=0.50 ATR", dict(chase_k=0.50)),
        ("chase<=1.00 ATR", dict(chase_k=1.00)),
        ("gap-dn skip", dict(gapdn=True)),
        ("gap-dn + chase 0.5", dict(gapdn=True, chase_k=0.50)),
    ]
    print("=" * 104)
    print("H9 GAP POLICY - entry filters (anchor: n=28630 PF=1.34 avg=+1.02)")
    print("=" * 104)
    for ci, (label, kw) in enumerate(configs):
        tr = run(bundles, rs_panel, **kw)
        if ci == 0:
            s = stats(tr)
            ok = (s["trades"] == 28630 and abs(s["profit_factor"] - 1.34) < 0.01
                  and s["avg_ret_pct"] == 1.02)
            print(f"anchor check: n={s['trades']} PF={s['profit_factor']} "
                  f"avg={s['avg_ret_pct']} -> {'OK' if ok else 'MISMATCH - ABORT'}")
            if not ok:
                raise SystemExit(1)
        print(f"[{label}]")
        brief(tr, trend, "  full:")
        brief(tr[tr["rs90"]], trend, "  RS>=90:")

    print("\n--- realism check: PLAN-anchored stops (resting SL behaviour) ---")
    for label, kw in [("V0 baseline", {}), ("gap-dn + chase 0.5", dict(gapdn=True, chase_k=0.50))]:
        tr = run(bundles, rs_panel, plan_anchor=True, **kw)
        print(f"[{label} + plan-anchor]")
        brief(tr, trend, "  full:")
        brief(tr[tr["rs90"]], trend, "  RS>=90:")


if __name__ == "__main__":
    main()
