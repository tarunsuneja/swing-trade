#!/usr/bin/env python3
"""H11 - Setup quality score (Phase 1.3).

Score out of 100 from already-validated information ONLY:

    RS percentile        35   (rs_panel / 99)
    trend quality        25   (ATRs above rising SMA200, 0..10 -> 0..1)
    dist from SMA20      15   (0 ATR above = best, 3+ ATR = 0)
    volatility quality   15   (ATR14/close <=3% best, >=8% zero)
    volume confirm       10   (trigger-day vol vs VOL20, 2x = full)

User's original reward/risk weight (10%) was dropped: under the fixed
2R target every candidate has IDENTICAL planned R:R, so the component
is degenerate. Weights renormalised instead of padding dead weight.

Validation gate: score DECILES must be monotone (low scores should be
the weak trades). No cutoff gets adopted unless the gradient is real;
display-ranking value exists even without one.
"""
import numpy as np
import pandas as pd

import strategy_validation as sv

W_RS, W_TREND, W_DIST, W_VOLQ, W_VOL = .35, .25, .15, .15, .10


def clip01(x):
    return float(min(max(x, 0.0), 1.0))


def score_row(rs_now, c, sma200, sma20, atr, vol, vol20):
    if not (np.isfinite(rs_now) and np.isfinite(sma200)
            and np.isfinite(atr) and atr > 0):
        return None
    atrp = atr / c

    rs_c = clip01((rs_now / 99.0) / 0.999)

    atrs_above = (c - sma200) / atr
    trend_c = clip01(atrs_above / 10.0)

    dist_atr = (c - sma20) / atr
    dist_c = clip01(1.0 - max(dist_atr, 0.0) / 3.0)

    volq_c = clip01(1.0 - (atrp - 0.03) / 0.05) if atrp > 0.03 else 1.0

    vol_c = (clip01(float(vol) / float(vol20) / 2.0)
             if np.isfinite(vol20) and vol20 > 0 else 0.5)

    return round(100 * (W_RS * rs_c + W_TREND * trend_c + W_DIST * dist_c
                        + W_VOLQ * volq_c + W_VOL * vol_c), 1)


def main():
    from strategy_validation import COST_PCT
    data, _ = sv.load_data()
    px = pd.DataFrame({tk: d["Close"] for tk, d in data.items()})
    rs_panel = ((px / px.shift(252) - 1).rank(axis=1, pct=True) * 99)

    nifty = pd.read_csv(os.path.join(sv.os.path.dirname(
        os.path.abspath(__file__)), "_price_cache", "NIFTY.csv"),
        parse_dates=["date"], index_col="date")
    trend = (nifty["Close"] > nifty["Close"].rolling(200).mean()).fillna(False)
    trend.index = trend.index.tz_localize(None)

    rows = []
    for tk, df in data.items():
        sigs = sv.signals(df)["pullback"]
        if len(sigs) == 0:
            continue
        o = df["Open"].to_numpy(float)
        h = df["High"].to_numpy(float)
        l = df["Low"].to_numpy(float)
        atr = df["ATR"].to_numpy(float)
        dates = df.index
        for d in sigs:
            i = dates.searchsorted(d)
            if i + 1 >= len(dates):
                continue
            r = df.iloc[i]
            rs_now = float(rs_panel.at[d, tk]) if tk in rs_panel.columns else np.nan
            sc = score_row(rs_now, float(r["Close"]), float(r["SMA200"]),
                           float(r["SMA20"]), float(r["ATR"]),
                           r["Volume"], r.get("VOL20", np.nan))
            if sc is None:
                continue
            # --- exact BASE exit engine (buf.25 lb5 2R ts20) ---
            entry = o[i + 1]
            if not np.isfinite(entry) or entry <= 0:
                continue
            a = atr[i]
            lo = l[max(0, i - 4):i + 1].min()
            stop = min(lo, entry - 2 * a) - 0.25 * a
            tgt = entry + 2 * (entry - stop)
            exit_px, exit_i = None, None
            for j in range(i + 1, min(i + 21, len(dates))):
                if l[j] <= stop:
                    exit_px, exit_i = stop, j
                    break
                if h[j] >= tgt:
                    exit_px, exit_i = tgt, j
                    break
            if exit_px is None:
                j = min(i + 20, len(dates) - 1)
                exit_px, exit_i = o[j], j
            net = ((exit_px / entry - 1) - COST_PCT / 100) * 100
            risk = (entry - stop) / entry
            rows.append({"ticker": tk, "entry_date": dates[i + 1],
                         "exit_date": dates[exit_i],
                         "ret_pct": round(net, 2),
                         "r": round(net / 100 / risk, 2) if risk > 0 else np.nan,
                         "score": sc,
                         "rs": round(rs_now, 1),
                         "gate_ok": bool(trend.asof(dates[i]))})

    tr = pd.DataFrame(rows)
    tr.to_csv("_score_trades.csv", index=False)
    print(f"trades scored: {len(tr)} "
          f"(score mean {tr['score'].mean():.1f}, "
          f"p5 {tr['score'].quantile(.05):.0f}, p95 {tr['score'].quantile(.95):.0f})")

    print("\n--- ALL pullback trades by score DECILE (1=lowest) ---")
    tr["dec"] = pd.qcut(tr["score"], 10, labels=False, duplicates="drop") + 1
    g = tr.groupby("dec").agg(n=("ret_pct", "size"), win=("ret_pct",
                              lambda x: f"{100*(x>0).mean():.0f}%"),
                              avg=("ret_pct", "mean"),
                              pf=("ret_pct", lambda x: round(
                                  x[x > 0].sum() / abs(x[x <= 0].sum()), 2)))
    print(g.to_string())

    r90 = tr[tr["rs"] >= 90]
    print(f"\n--- RS>=90 book ({len(r90)} trades) by score QUARTILE ---")
    r90 = r90.copy()
    r90["q"] = pd.qcut(r90["score"], 4, labels=False, duplicates="drop") + 1
    g2 = r90.groupby("q").agg(n=("ret_pct", "size"),
                              win=("ret_pct", lambda x: f"{100*(x>0).mean():.0f}%"),
                              avg=("ret_pct", "mean"),
                              pf=("ret_pct", lambda x: round(
                                  x[x > 0].sum() / abs(x[x <= 0].sum()), 2)))
    print(g2.to_string())

    # gated portfolio view: drop bottom-X% by score
    print("\n--- gated portfolio impact (RS>=90 book, score cutoffs) ---")
    for cut in (None, 30, 40, 50):
        sub = r90 if cut is None else r90[r90["score"] >= cut]
        p = sv.portfolio_cagr(sub, trend)
        if p:
            print(f"cut>={cut}: taken={p['taken']:>4} "
                  f"CAGR={p['cagr_pct']:>5}% DD={p['max_dd_pct']:>6}%")


if __name__ == "__main__":
    import os
    main()
