"""Validate POST-CRASH COOLDOWN filter (earnings-shock proxy), Aug 21 2026.

Motivation: BHARATFORG Tier-II setup (Aug 21) sat on a fresh Q1 net loss /
9% results-day gap-down. Question: does skipping new entries on stocks that
recently gapped down hard improve any adopted strategy?

Filter B (price-only, no fundamentals needed):
  a stock is IN COOLDOWN on day t if within the prior W sessions it had an
  overnight gap <= THR on volume >= VOLX x VOL20.
  Variants: C1 (-5%, 1.5x, W=5)  C2 (-5%, 1.5x, W=10)
            C3 (-4%, 1.2x, W=5)  C4 (-7%, 2.0x, W=5)

Tested on all three adopted strategies: TREND PULLBACK (+RS>=90 subset),
BB REVERSION, TIER-II SYMPATHY. Filters REMOVE signals only; exits/slots/
costs identical to strategy_validation.py. Baselines must reproduce the
published JSON numbers first.

Fundamental gate note: TV screener exposes no fundamentals and yfinance
carries only ~5 quarters -> a PAT<0 hard gate is UNVALIDATABLE; info-only.

Run:  py -X utf8 test_earnings_filter.py
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

CONFIGS = [
    ("C1 -5%/1.5x/5d", -0.05, 1.5, 5),
    ("C2 -5%/1.5x/10d", -0.05, 1.5, 10),
    ("C3 -4%/1.2x/5d", -0.04, 1.2, 5),
    ("C4 -7%/2.0x/5d", -0.07, 2.0, 5),
]


def crash_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    gap = df["Open"] / df["Close"].shift(1) - 1
    out = {}
    for label, thr, volx, w in CONFIGS:
        cr = ((gap <= thr) & (df["Volume"] >= volx * df["VOL20"])).fillna(False)
        out[label] = cr.shift(1).rolling(w).sum().gt(0).fillna(False)
    return out


def brief(tr: pd.DataFrame, trend: pd.Series, label: str) -> None:
    s = stats(tr)
    if not s.get("trades"):
        print(f"  {label:<26} no trades")
        return
    up = tr["entry_date"].map(lambda d: bool(trend.asof(d)))
    s_up = stats(tr[up])
    e17 = stats(tr[tr["exit_date"] < pd.Timestamp("2018-01-01")])
    e26 = stats(tr[tr["exit_date"] >= pd.Timestamp("2018-01-01")])
    p = portfolio_cagr(tr, trend)
    pg = (f"CAGR={p['cagr_pct']:>5}% DD={p['max_dd_pct']:>6}% took={p['taken']}"
          if p else "no portfolio")
    print(f"  {label:<26} n={s['trades']:>5} win={s['win_pct']:>5}% "
          f"avg={s['avg_ret_pct']:>+6}% PF={s['profit_factor']:>5} "
          f"upPF={s_up.get('profit_factor', '-'):>5} "
          f"e17PF={e17.get('profit_factor', '-'):>5} "
          f"e26PF={e26.get('profit_factor', '-'):>5} | {pg}")


def boot_ci(tr: pd.DataFrame, mask: pd.Series, n_boot: int = 1000,
            seed: int = 7) -> str:
    rng = np.random.default_rng(seed)
    a = tr.loc[mask, "ret_pct"].to_numpy(float)
    b = tr.loc[~mask, "ret_pct"].to_numpy(float)
    if len(a) < 30 or len(b) < 30:
        return f"n/a (flagged n={len(a)})"
    diffs = np.empty(n_boot)
    for k in range(n_boot):
        diffs[k] = rng.choice(a, len(a)).mean() - rng.choice(b, len(b)).mean()
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return f"[{lo:+.2f}, {hi:+.2f}] (flagged n={len(a)})"


def tag_trades(data, universe, kind: str, sig_key: str | None = None):
    rows, flags = [], {}
    for tk in universe:
        df = data.get(tk)
        if df is None or len(df) < 300:
            continue
        df.attrs["ticker"] = tk
        sigs = signals(df)[sig_key or kind]
        if len(sigs) == 0:
            continue
        cm = crash_masks(df)
        rows += simulate(df, sigs, kind)
        for d in sigs:
            i = df.index.searchsorted(d)
            if i + 1 >= len(df):
                continue
            e = df["Open"].iloc[i + 1]
            if not np.isfinite(e) or e <= 0:
                continue
            flags[(tk, df.index[i + 1])] = tuple(
                bool(m.iloc[i]) for m in cm.values())
    tr = pd.DataFrame(rows)
    if tr.empty:
        return tr
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["exit_date"] = pd.to_datetime(tr["exit_date"])
    fl = [flags.get((t, e)) for t, e in zip(tr["ticker"], tr["entry_date"])]
    for j, (label, *_ ) in enumerate(CONFIGS):
        tr[label] = [bool(f[j]) if f else False for f in fl]
    return tr


def main() -> None:
    universe = get_universe()
    data, nifty = load_data()
    trend = (nifty["Close"] > nifty["Close"].rolling(200).mean()).fillna(False)
    trend.index = trend.index.tz_localize(None)

    closes = {tk: d["Close"] for tk, d in data.items()
              if d is not None and len(d) >= 300}
    px = pd.DataFrame(closes)
    rs_panel = ((px / px.shift(252) - 1).rank(axis=1, pct=True) * 99)

    # ---------- PULLBACK ----------
    print("=" * 100)
    print("PULLBACK (baseline anchor: n=28630 PF=1.34 gated 13.7%)")
    print("=" * 100)
    tr = tag_trades(data, universe, "pullback")
    r90 = pd.Series([
        float(rs_panel.at[e, t]) >= 90
        if t in rs_panel.columns and e in rs_panel.index else False
        for t, e in zip(tr["ticker"], tr["entry_date"])])
    brief(tr, trend, "BASELINE")
    brief(tr[r90], trend, "BASELINE RS>=90")
    for label, *_ in CONFIGS:
        brief(tr[~tr[label]], trend, f"skip if cooldown {label}")
    print("  -- RS>=90 subset --")
    brief(tr[r90], trend, "RS90 BASELINE")
    for label, *_ in CONFIGS:
        brief(tr[r90 & ~tr[label]], trend, f"RS90 skip {label}")
    print(f"\n  bootstrap mean-diff flagged-vs-clean (within RS90, C1): "
          f"{boot_ci(tr[r90], tr.loc[r90, CONFIGS[0][0]])}")

    # ---------- BB REVERSION ----------
    print("\n" + "=" * 100)
    print("BB REVERSION")
    print("=" * 100)
    tb = tag_trades(data, universe, "bb_reversion")
    brief(tb, trend, "BASELINE")
    for label, *_ in CONFIGS:
        brief(tb[~tb[label]], trend, f"skip if cooldown {label}")

    # ---------- TIER-II SYMPATHY ----------
    print("\n" + "=" * 100)
    print("TIER-II SYMPATHY (validated: n=66 PF=1.61)")
    print("=" * 100)
    import test_tier2_sympathy as t2
    smap = t2.get_sector_map(universe)
    sig = t2.build_signals(data, smap)
    rows, flags = [], {}
    for sym, grp in sig.groupby("symbol"):
        df = data.get(sym)
        if df is None:
            continue
        df.attrs["ticker"] = sym
        idx = pd.DatetimeIndex([d for d in grp.date if d in df.index])
        cm = crash_masks(df)
        rows += t2.simulate_sympathy(df, idx)
        for d in idx:
            i = df.index.searchsorted(d)
            if i + 1 >= len(df):
                continue
            e = df["Open"].iloc[i + 1]
            if not np.isfinite(e) or e <= 0:
                continue
            flags.setdefault((sym, df.index[i + 1]), tuple(
                bool(m.iloc[i]) for m in cm.values()))
    tt = pd.DataFrame(rows)
    tt["entry_date"] = pd.to_datetime(tt["entry_date"])
    tt["exit_date"] = pd.to_datetime(tt["exit_date"])
    fl = [flags.get((t, e)) for t, e in zip(tt["ticker"], tt["entry_date"])]
    for j, (label, *_) in enumerate(CONFIGS):
        tt[label] = [bool(f[j]) if f else False for f in fl]
    brief(tt, trend, "BASELINE")
    for label, *_ in CONFIGS:
        brief(tt[~tt[label]], trend, f"skip if cooldown {label}")

    print("\nNote: fundamental PAT<0 gate is unvalidatable (no point-in-time")
    print("quarterly data older than Mar-2025); display-column only.")


if __name__ == "__main__":
    main()
