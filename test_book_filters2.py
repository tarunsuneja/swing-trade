"""Book-filter research round 2 (doc s16 follow-up, Aug 21 2026).

PART A -- quality filters stacked on validated TREND PULLBACK:
  H3  Elder Triple Screen: weekly-trend check before the daily entry.
      W1 = weekly close > weekly EMA(26); W2 = W1 + EMA rising 4 weeks.
      No lookahead: only COMPLETED weeks are used (shift 1).
  H4  Gujral ADX: Wilder ADX(14) >= 25 (trend strength), softer >= 20.
  Combo of the best weekly variant + ADX.

PART B -- can the failed 52w-high breakout be rescued (Minervini/O'Neil)?
  Original hi52 gates (close>=98% of 252d-high, >SMA200, RSI 60-75,
  vol>1.2x avg) PLUS: volume >= 1.4x avg AND volatility-contraction proxy
  (15-day range < 0.7x the prior 45-day range before the base).

Method: same as test_momentum_filters.py -- filters REMOVE signals only;
exits/slots/costs identical to strategy_validation.py. Baseline reproduces
the published JSON numbers first. Validation battery on every candidate:
era splits, ADX threshold sweep (monotonicity), RS>=90 stacking check,
bootstrap CI on mean-return difference, portfolio capacity counts.

Run:  py -X utf8 test_book_filters2.py
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
    wilder,
)


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    up, dn = h.diff(), -l.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    atr = wilder(tr, n)
    pdi = 100 * wilder(plus_dm, n) / atr
    mdi = 100 * wilder(minus_dm, n) / atr
    dx = (100 * (pdi - mdi).abs() / (pdi + mdi)).replace([np.inf], np.nan)
    return wilder(dx.fillna(0), n)


def weekly_trend(df: pd.DataFrame, span: int = 26) -> tuple[pd.Series, pd.Series]:
    """Weekly close vs EMA(span), COMPLETED weeks only -> no lookahead."""
    wk = df["Close"].resample("W-FRI").last().dropna()
    ema = wk.ewm(span=span, adjust=False).mean()
    w = pd.DataFrame({"above": wk > ema,
                      "rising": ema > ema.shift(4)}).shift(1)
    out = w.reindex(df.index, method="ffill")
    return out["above"].eq(True), out["rising"].eq(True)


def breakout_v2_signals(df: pd.DataFrame) -> pd.DatetimeIndex:
    """hi52 gates + stronger volume + contraction proxy."""
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    s_hi = ((c >= 0.98 * df["HI252"]) & (c > df["SMA200"])
            & (df["RSI"].between(60, 75)) & (v > 1.2 * df["VOL20"])
            & df["HI252"].notna()).fillna(False)
    hh15, ll15 = h.rolling(15).max(), l.rolling(15).min()
    hh45, ll45 = h.rolling(45).max().shift(15), l.rolling(45).min().shift(15)
    compressed = ((hh15 - ll15) / c < 0.7 * (hh45 - ll45) / c).fillna(False)
    sig = s_hi & compressed & v.ge(1.4 * df["VOL20"]).fillna(False)
    idx = df.index[sig]
    return idx[idx >= df.index[260]]


def line(label: str, s: dict) -> None:
    print(f"  {label:<22} n={s['trades']:>5}  win={s['win_pct']:>6}%  "
          f"avg={s['avg_ret_pct']:>+7.2f}%  R={s['avg_r']:>+5.2f}  "
          f"PF={s['profit_factor']:>5}  maxDD={s['max_dd_eq_curve']:>6.1f}%")


def boot_ci(tr: pd.DataFrame, mask: pd.Series, n_boot: int = 1000,
            seed: int = 7) -> str:
    """Bootstrap 95% CI of mean(ret_pct): masked subset minus complement."""
    rng = np.random.default_rng(seed)
    a = tr.loc[mask, "ret_pct"].to_numpy(float)
    b = tr.loc[~mask, "ret_pct"].to_numpy(float)
    if len(a) < 30 or len(b) < 30:
        return "n/a (small n)"
    diffs = np.empty(n_boot)
    for k in range(n_boot):
        diffs[k] = rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean()
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return f"[{lo:+.2f}, {hi:+.2f}]  (n_a={len(a)}, n_b={len(b)})"


def evaluate(tr: pd.DataFrame, mask: pd.Series, nifty_trend: pd.Series,
             label: str) -> dict:
    sub = tr[mask]
    s_all = stats(sub)
    if not s_all.get("trades"):
        print(f"\n{label}: no trades")
        return {}
    tmask = sub["entry_date"].map(lambda d: bool(nifty_trend.asof(d)))
    p_g = portfolio_cagr(sub, nifty_trend)
    print(f"\n{label}")
    line("overall", s_all)
    for nm, m2 in (("in Nifty-uptrend", tmask), ("era 2010-2017",
                   sub["exit_date"] < pd.Timestamp("2018-01-01")),
                   ("era 2018-2026",
                   sub["exit_date"] >= pd.Timestamp("2018-01-01"))):
        s2 = stats(sub[m2])
        if s2.get("trades"):
            line(nm, s2)
    if p_g:
        print(f"  portfolio GATED          CAGR={p_g['cagr_pct']}%  "
              f"final=Rs.{p_g['final_equity']:,}  maxDD={p_g['max_dd_pct']}%  "
              f"(took {p_g['taken']})")
    return s_all


def main() -> None:
    universe = get_universe()
    data, nifty = load_data()
    nifty_trend = (nifty["Close"] > nifty["Close"].rolling(200).mean()).fillna(False)
    nifty_trend.index = nifty_trend.index.tz_localize(None)

    # ---------- PART A: pullback filter stack ----------
    rows, flags, closes = [], {}, {}
    for tk in universe:
        df = data.get(tk)
        if df is None or len(df) < 300:
            continue
        df.attrs["ticker"] = tk
        closes[tk] = df["Close"]
        sigs = signals(df)["pullback"]
        if len(sigs) == 0:
            continue
        w_above, w_rising = weekly_trend(df)
        adx14 = adx(df)
        rows += simulate(df, sigs, "pullback")
        for d in sigs:
            i = df.index.searchsorted(d)
            if i + 1 >= len(df):
                continue
            e = df["Open"].iloc[i + 1]
            if not np.isfinite(e) or e <= 0:
                continue
            flags[(tk, df.index[i + 1])] = (
                bool(w_above.iloc[i]), bool(w_rising.iloc[i]),
                float(adx14.iloc[i]), d)

    tr = pd.DataFrame(rows)
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["exit_date"] = pd.to_datetime(tr["exit_date"])
    fl = [flags.get((t, e)) for t, e in zip(tr["ticker"], tr["entry_date"])]
    tr["w_above"] = [bool(f[0]) if f else False for f in fl]
    tr["w_rising"] = [bool(f[1]) if f else False for f in fl]
    tr["adx"] = [f[2] if f else np.nan for f in fl]

    # Cross-sectional RS panel (same construction as adopted s16 gate),
    # tagged at the SIGNAL day to match test_momentum_filters.py exactly.
    px = pd.DataFrame(closes)
    rs_panel = ((px / px.shift(252) - 1).rank(axis=1, pct=True) * 99)
    tr["rs"] = [
        float(rs_panel.at[f[3], t])
        if f and f[3] in rs_panel.index and t in rs_panel.columns else np.nan
        for t, f in zip(tr["ticker"], fl)]

    print("=" * 72)
    print("PART A - PULLBACK with book filters (baseline PF 1.34 / gated 13.7%)")
    print("=" * 72)
    evaluate(tr, pd.Series(True, index=tr.index), nifty_trend,
             "BASELINE pullback")
    evaluate(tr, tr["w_above"], nifty_trend, "H3a: weekly >EMA26")
    evaluate(tr, tr["w_above"] & tr["w_rising"], nifty_trend,
             "H3b: weekly >EMA26 rising")
    evaluate(tr, tr["adx"] >= 25, nifty_trend, "H4a: ADX>=25")
    evaluate(tr, tr["adx"] >= 20, nifty_trend, "H4b: ADX>=20")
    evaluate(tr, tr["w_above"] & tr["w_rising"] & (tr["adx"] >= 20),
             nifty_trend, "COMBO: W2 + ADX>=20")

    # --- validation battery: monotonicity, stacking, significance ---
    for thr in (15, 20, 25, 30, 35):
        evaluate(tr, tr["adx"] >= thr, nifty_trend,
                 f"SWEEP ADX>={thr} (monotonic?)")
    r90 = tr["rs"] >= 90
    evaluate(tr, r90, nifty_trend, "REF: RS>=90 (adopted)")
    evaluate(tr, r90 & (tr["adx"] >= 25), nifty_trend,
             "STACK: RS>=90 & ADX>=25")
    evaluate(tr, r90 & (tr["adx"] >= 20), nifty_trend,
             "STACK: RS>=90 & ADX>=20")

    print("\nBootstrap 95% CI of mean(ret_pct): subset minus complement")
    print(f"  H4a ADX>=25        {boot_ci(tr, tr['adx'] >= 25)}")
    print(f"  H3b weekly-rising  {boot_ci(tr, tr['w_above'] & tr['w_rising'])}")
    print(f"  REF RS>=90         {boot_ci(tr, r90)}")
    print(f"  STACK R90&ADX25    {boot_ci(tr, r90 & (tr['adx'] >= 25))}")

    # ---------- PART B: breakout rescue ----------
    print("\n" + "=" * 72)
    print("PART B - BREAKOUT-V2 rescue attempt (original hi52: PF 0.94 REJECTED)")
    print("=" * 72)
    b_rows = {"orig": [], "v2": []}
    for tk in universe:
        df = data.get(tk)
        if df is None or len(df) < 300:
            continue
        df.attrs["ticker"] = tk
        b_rows["orig"] += simulate(df, signals(df)["hi52"], "hi52")
        b_rows["v2"] += simulate(df, breakout_v2_signals(df), "hi52")

    for key, label in (("orig", "BASELINE hi52 (re-run)"), ("v2", "BREAKOUT-V2")):
        t2 = pd.DataFrame(b_rows[key])
        if t2.empty:
            print(f"\n{label}: no trades")
            continue
        t2["entry_date"] = pd.to_datetime(t2["entry_date"])
        t2["exit_date"] = pd.to_datetime(t2["exit_date"])
        evaluate(t2, pd.Series(True, index=t2.index), nifty_trend, label)

    print("\nNote: RS>=90 gate (adopted, s16) applies ON TOP of any future "
          "adoption here; today's tests isolate one variable at a time.")


if __name__ == "__main__":
    main()
