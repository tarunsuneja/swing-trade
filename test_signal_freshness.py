#!/usr/bin/env python3
"""H12 - Signal freshness / late-entry decay (Phase 1.4).

Scanner shows signals once; users act next morning at best. How fast
does the edge decay if entry happens k sessions AFTER the trigger?

Variants (anchor engine otherwise unchanged: buf .25 lb5 2R ts20,
RS>=90 book, regime gate at decision time):
  k=1        baseline (current behaviour)
  k=2..5     late entry at open of bar i+k, stop/target RECOMPUTED
             from the actual entry bar (what a late entrant would do)

Two regimes per k:
  unc   - enter regardless of what price did in between
  cond  - enter ONLY if the ORIGINAL 2R target was never touched
          between trigger and entry (don't chase a filled signal)

Gate: adopt an expiry rule only if decay is material and clean;
otherwise keep 'act on trigger day' guidance.
"""
import numpy as np
import pandas as pd

import strategy_validation as sv

COST_PCT = 0.55
HORIZON = 20


def sim_entry(o, h, l, atr, dates, i, k, orig_tgt):
    """Late entry at open of bar i+k. Returns net% or None."""
    j = i + k
    if j >= len(dates) - 0:
        return None
    entry = o[j]
    if not np.isfinite(entry) or entry <= 0:
        return None
    a = atr[j - 1]
    lo = l[max(0, j - 5):j].min()
    stop = min(lo, entry - 2 * a) - 0.25 * a
    tgt = entry + 2 * (entry - stop)
    exit_px = None
    for m in range(j, min(j + HORIZON, len(dates))):
        if l[m] <= stop:
            exit_px = stop
            break
        if h[m] >= tgt:
            exit_px = tgt
            break
    if exit_px is None:
        m = min(j + HORIZON - 1, len(dates) - 1)
        exit_px = o[m]
    risk = (entry - stop) / entry
    if risk <= 0:
        return None
    return (((exit_px / entry - 1) - COST_PCT / 100) / risk * 100,
            ((exit_px / entry - 1) - COST_PCT / 100) * 100)


def main():
    data, _ = sv.load_data()
    px = pd.DataFrame({tk: d["Close"] for tk, d in data.items()})
    rs_panel = ((px / px.shift(252) - 1).rank(axis=1, pct=True) * 99)

    import os
    nifty = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "_price_cache", "NIFTY.csv"),
                        parse_dates=["date"], index_col="date")
    trend = (nifty["Close"] > nifty["Close"].rolling(200).mean()).fillna(False)
    trend.index = trend.index.tz_localize(None)

    # results[k][regime] -> list of R multiples
    res = {k: {"unc": [], "cond": [], "pct_unc": [], "pct_cond": []}
           for k in (1, 2, 3, 5)}
    missed_target = {k: 0 for k in (2, 3, 5)}

    for tk, df in data.items():
        sigs = sv.signals(df)["pullback"]
        if len(sigs) == 0:
            continue
        o = df["Open"].to_numpy(float)
        h = df["High"].to_numpy(float)
        l = df["Low"].to_numpy(float)
        c = df["Close"].to_numpy(float)
        atr = df["ATR"].to_numpy(float)
        dates = df.index
        for d in sigs:
            i = dates.searchsorted(d)
            if tk not in rs_panel.columns or float(rs_panel.at[d, tk]) < 90:
                continue
            if i + 1 >= len(dates) or not np.isfinite(atr[i]) or atr[i] <= 0:
                continue
            if not bool(trend.asof(dates[min(i + 4, len(dates) - 1)])):
                continue
            a = atr[i]
            lo = l[max(0, i - 4):i + 1].min()
            e1 = o[i + 1]
            if not np.isfinite(e1) or e1 <= 0:
                continue
            stop1 = min(lo, e1 - 2 * a) - 0.25 * a
            orig_tgt = e1 + 2 * (e1 - stop1)

            r1 = sim_entry(o, h, l, atr, dates, i, 1, orig_tgt)
            if r1 is None:
                continue
            res[1]["unc"].append(r1[0]); res[1]["pct_unc"].append(r1[1])
            res[1]["cond"].append(r1[0]); res[1]["pct_cond"].append(r1[1])

            for k in (2, 3, 5):
                # was original target touched between entry-day and k-1?
                ran = (h[i + 1:min(i + k, len(dates))] >= orig_tgt).any() \
                    if i + k <= len(dates) else True
                rk = sim_entry(o, h, l, atr, dates, i, k, orig_tgt)
                if rk is None:
                    continue
                res[k]["unc"].append(rk[0]); res[k]["pct_unc"].append(rk[1])
                if ran:
                    missed_target[k] += 1
                    continue
                res[k]["cond"].append(rk[0]); res[k]["pct_cond"].append(rk[1])

    def pf(x):
        x = pd.Series(x)
        pos, neg = x[x > 0].sum(), abs(x[x <= 0].sum())
        return round(pos / neg, 2) if neg > 0 else float("inf")

    print(f"{'k':>2} {'regime':<5} {'n':>6} {'win%':>6} {'avg%':>7} "
          f"{'avg R':>7} {'PF':>6}")
    base = None
    for k in (1, 2, 3, 5):
        for reg in ("unc", "cond"):
            r = res[k][reg]
            p = res[k]["pct_" + reg]
            s = f"{k:>2} {reg:<5} {len(r):>6} {100*np.mean(np.array(p)>0):>6.1f} " \
                f"{np.mean(p):>+7.2f} {np.mean(r):>+7.3f} {pf(r):>6}"
            print(s)
            if k == 1 and reg == "unc":
                base = (np.mean(r), np.mean(p))

    print("\ndecay vs k=1 baseline (unc regime):")
    for k in (2, 3, 5):
        rr = np.mean(res[k]["unc"]) / base[0]
        pp = np.mean(res[k]["pct_unc"]) / base[1]
        skipped = missed_target[k]
        print(f"  k={k}: R-retention {rr*100:.0f}%  %-retention {pp*100:.0f}%"
              f"  (cond-regime excluded {skipped} already-filled signals)")


if __name__ == "__main__":
    main()
