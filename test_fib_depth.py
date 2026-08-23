"""H7 - Fib retracement depth filter on PULLBACK entries (from 'Indicator X'
auto golden pocket idea), Aug 21 2026.

Hypothesis: pullback entries work better when the dip has retraced a
meaningful fraction (0.5-0.65 'golden pocket') of the prior up-swing,
i.e. enter on reclaim AFTER a deep enough pullback, not on shallow dips.

Definitions (all causal - only confirmed data used at signal time):
  SH      = most recent CONFIRMED pivot high (k=3 bars each side),
            formed at bar j <= i-3
  SL_prev = lowest low in the 15 bars BEFORE the rally into SH (j-15..j)
  trough  = lowest low between SH bar and signal day i (inclusive)
  depth   = (SH - trough) / (SH - SL_prev)

Variants: depth>=0.382, >=0.5, >=0.618, golden-pocket zone 0.5<=d<=0.786.
Evaluated on full PULLBACK set + RS>=90 subset; baselines must reproduce
published anchors (n=28630 PF=1.34 / RS90 n=4936 PF=1.55).

Run:  py -X utf8 test_fib_depth.py
"""
import numpy as np
import pandas as pd

from strategy_validation import (
    get_universe,
    load_data,
    portfolio_cagr,
    signals,
    simulate,
    stats,
)

K = 3        # pivot confirmation bars each side
W_PREV = 15  # lookback for pre-swing low


def tag_with_depth(data, universe):
    rows, depths = [], {}
    for tk in universe:
        df = data.get(tk)
        if df is None or len(df) < 300:
            continue
        df.attrs["ticker"] = tk
        sigs = signals(df)["pullback"]
        if len(sigs) == 0:
            continue
        rows += simulate(df, sigs, "pullback")

        hi, lo = df["High"].to_numpy(float), df["Low"].to_numpy(float)
        n = len(df)
        # confirmed pivot highs: hi[j] is max of j-K..j+K, strict on right
        piv_j = []
        for j in range(K, n - K):
            w = hi[j - K:j + K + 1]
            if hi[j] == w.max() and (hi[j] > hi[j + 1:j + K + 1]).all():
                piv_j.append(j)
        pi = 0
        for d in sigs:
            i = df.index.searchsorted(d)
            if i + 1 >= len(df):
                continue
            while pi < len(piv_j) and piv_j[pi] + K <= i:
                pi += 1
            if pi == 0:
                continue
            j = piv_j[pi - 1]
            if j >= i:
                continue
            sl_prev = lo[max(0, j - W_PREV):j + 1].min()
            trough = lo[j:i + 1].min()
            rng = hi[j] - sl_prev
            depths[(tk, df.index[i + 1])] = (
                (hi[j] - trough) / rng if rng > 0 else np.nan)
    tr = pd.DataFrame(rows)
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["exit_date"] = pd.to_datetime(tr["exit_date"])
    tr["depth"] = [depths.get((t, e), np.nan)
                   for t, e in zip(tr["ticker"], tr["entry_date"])]
    return tr


def brief(tr, trend, label):
    s = stats(tr)
    if not s.get("trades"):
        print(f"  {label:<24} no trades")
        return
    up = tr["entry_date"].map(lambda d: bool(trend.asof(d)))
    s_up = stats(tr[up])
    e17 = stats(tr[tr["exit_date"] < pd.Timestamp("2018-01-01")])
    e26 = stats(tr[tr["exit_date"] >= pd.Timestamp("2018-01-01")])
    p = portfolio_cagr(tr, trend)
    pg = (f"CAGR={p['cagr_pct']:>5}% DD={p['max_dd_pct']:>6}% took={p['taken']}"
          if p else "no portfolio")
    print(f"  {label:<24} n={s['trades']:>5} win={s['win_pct']:>5}% "
          f"avg={s['avg_ret_pct']:>+6}% PF={s['profit_factor']:>5} "
          f"upPF={s_up.get('profit_factor', '-'):>5} "
          f"e17PF={e17.get('profit_factor', '-'):>5} "
          f"e26PF={e26.get('profit_factor', '-'):>5} | {pg}")


def main():
    universe = get_universe()
    data, nifty = load_data()
    trend = (nifty["Close"] > nifty["Close"].rolling(200).mean()).fillna(False)
    trend.index = trend.index.tz_localize(None)

    closes = {tk: d["Close"] for tk, d in data.items()
              if d is not None and len(d) >= 300}
    px = pd.DataFrame(closes)
    rs_panel = ((px / px.shift(252) - 1).rank(axis=1, pct=True) * 99)

    print("building trades + depth tags ...")
    tr = tag_with_depth(data, universe)

    s = stats(tr)
    ok = (s["trades"] == 28630 and abs(s["profit_factor"] - 1.34) < 0.01)
    print(f"anchor check: n={s['trades']} PF={s['profit_factor']} "
          f"-> {'OK' if ok else 'MISMATCH'}")
    if not ok:
        raise SystemExit(1)

    r90 = pd.Series([
        bool(t in rs_panel.columns and e in rs_panel.index
             and rs_panel.at[e, t] >= 90)
        for t, e in zip(tr["ticker"], tr["entry_date"])])

    d = tr["depth"]
    print(f"\ndepth distribution (n={int(d.notna().sum())}): "
          f"median={d.median():.2f} p25={d.quantile(.25):.2f} "
          f"p75={d.quantile(.75):.2f}")

    masks = [
        ("BASELINE (all)", pd.Series(True, index=tr.index)),
        ("depth>=0.382", d >= 0.382),
        ("depth>=0.50", d >= 0.50),
        ("depth>=0.618", d >= 0.618),
        ("GP zone .50-.786", (d >= 0.50) & (d <= 0.786)),
    ]
    print("\n" + "=" * 104)
    print("FULL PULLBACK SET")
    print("=" * 104)
    for label, m in masks:
        brief(tr[m.fillna(False)], trend, label)

    print("\n" + "=" * 104)
    print("RS>=90 SUBSET (the traded book)")
    print("=" * 104)
    for label, m in masks:
        brief(tr[r90 & m.fillna(False)], trend, label)


if __name__ == "__main__":
    main()
