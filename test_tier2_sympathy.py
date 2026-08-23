"""Scan E candidate: Tier II sympathy plays (McCall & Whistler, ch 8).

Hypothesis: when a sector leader (largest mcap in its sector) makes a big
up move on heavy volume, same-sector correlated stocks that have NOT yet
moved catch up within days. Buy the laggard at next open.

Codified rules:
  signal day t for candidate C with leader L (same sector, L = largest
  mcap symbol of that sector in our universe):
    - L return(t) >= +5% and L volume(t) >= 2 x L VOL20      (leader event)
    - corr(ret_C, ret_L) over last 120d >= 0.55              (true sympathy)
    - C return(t) < L return(t) / 2                          (lag still exists)
    - C close > SMA200 and SMA200 rising over 20d            (our trend gate)
    - C liquidity: 50d avg turnover >= Rs.5 Cr
  entry: next open after t. exits: pullback-style - stop =
  min(5d low, entry-2ATR) - 0.25ATR; target 2R; time stop 10 days.
"""
import os
import time as _time

import numpy as np
import pandas as pd

from strategy_validation import (
    _cached,
    get_universe,
    load_data,
    simulate,
    stats,
    wilder,
)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_price_cache")
SECTOR_FP = os.path.join(CACHE_DIR, "sectors.csv")


def get_sector_map(symbols: list[str]) -> pd.DataFrame:
    """symbol -> (sector, market_cap), cached on disk."""
    if os.path.exists(SECTOR_FP):
        df = pd.read_csv(SECTOR_FP)
        if len(df) >= 0.9 * len(symbols) and df["sector"].notna().all():
            return df.set_index("symbol")
    from tradingview_screener import Query, col

    _, df = (
        Query().set_markets("india")
        .select("name", "sector", "market_cap_basic")
        .where(col("type") == "stock", col("exchange") == "NSE",
               col("name").isin(symbols))
        .limit(len(symbols))
        .get_scanner_data()
    )
    out = df.rename(columns={"name": "symbol"})[["symbol", "sector", "market_cap_basic"]]
    if out["sector"].notna().sum() < 0.9 * len(out):
        raise RuntimeError(
            "TV screener returned degenerate sector data; keeping cache")
    out.to_csv(SECTOR_FP, index=False)
    return out.set_index("symbol")


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([df.High - df.Low,
                    (df.High - df.Close.shift()).abs(),
                    (df.Low - df.Close.shift()).abs()], axis=1).max(axis=1)
    return wilder(tr, n)


def build_signals(data: dict[str, pd.DataFrame],
                  smap: pd.DataFrame,
                  last_only: bool = False) -> pd.DataFrame:
    """Return one row per (candidate, signal_date).

    With last_only=True, only each leader's most recent event is evaluated
    (for live daily scanning); rows carry leader/corr/lret context.
    """
    # leaders = largest-mcap symbol per sector
    leaders = (smap.reset_index()
               .sort_values("market_cap_basic", ascending=False)
               .groupby("sector").head(1)["symbol"].tolist())
    leader_set = set(leaders)

    rets, vol_ok, liq_ok, uptrend = {}, {}, {}, {}
    for sym, df in data.items():
        r = df.Close.pct_change()
        rets[sym] = r
        vol_ok[sym] = df.Volume > 2 * df.Volume.rolling(20).mean()
        liq_ok[sym] = ((df.Close * df.Volume).rolling(50).mean() >= 5e7).reindex(r.index)
        c = df.Close
        uptrend[sym] = ((c > c.rolling(200).mean())
                        & (c.rolling(200).mean() > c.rolling(200).mean().shift(20))
                        ).reindex(r.index)

    R = pd.DataFrame(rets)
    rows = []
    sectors = smap["sector"].to_dict()

    for leader in leaders:
        sec = sectors.get(leader)
        if not sec or leader not in R.columns:
            continue
        mates = [s for s, x in sectors.items()
                 if x == sec and s != leader and s in R.columns]
        if not mates:
            continue

        l_ret = R[leader]
        l_evt = (l_ret >= 0.05) & vol_ok.get(leader, pd.Series(False, index=R.index))
        evt_dates = R.index[l_evt.fillna(False)]
        if last_only:
            evt_dates = evt_dates[-1:]
        if len(evt_dates) == 0:
            continue

        for mate in mates:
            corr = R[mate].rolling(120).corr(l_ret)
            up_s, lq_s = uptrend[mate], liq_ok[mate]
            for t in evt_dates:
                i = R.index.get_loc(t)
                if i < 130 or i + 1 >= len(R.index):
                    continue
                if not np.isfinite(corr.iloc[i]) or corr.iloc[i] < 0.55:
                    continue
                m_r = R[mate].iloc[i]
                l_r = l_ret.iloc[i]
                if not np.isfinite(m_r) or m_r >= l_r / 2:
                    continue
                if t not in up_s.index or t not in lq_s.index:
                    continue
                if not bool(up_s.loc[t]) or not bool(lq_s.loc[t]):
                    continue
                rows.append({"symbol": mate, "date": R.index[i + 1],
                             "leader": leader,
                             "corr": round(float(corr.iloc[i]), 2),
                             "leader_ret_pct": round(100 * float(l_ret.iloc[i]), 1)})
    sig_df = pd.DataFrame(rows).drop_duplicates()
    return sig_df


def simulate_sympathy(df: pd.DataFrame, sig_dates) -> list[dict]:
    """pullback-style exits with a faster 10-day time stop."""
    rows = []
    dates = df.index
    ATR = atr(df)
    for d in sig_dates:
        i = dates.searchsorted(d)
        if i + 1 >= len(df):
            continue
        entry = df.Open.iloc[i + 1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        a = ATR.iloc[i] if np.isfinite(ATR.iloc[i]) and ATR.iloc[i] > 0 else np.nan
        if not np.isfinite(a):
            continue
        stop = min(df.Low.iloc[i - 4:i + 1].min(), entry - 2 * a) - 0.25 * a
        tgt, tstop = entry + 2 * (entry - stop), 10
        exit_px, exit_i, reason = None, None, ""
        for j in range(i + 1, min(i + 1 + tstop, len(df))):
            if df.Low.iloc[j] <= stop:
                exit_px, exit_i, reason = stop, j, "stop"
                break
            if df.High.iloc[j] >= tgt:
                exit_px, exit_i, reason = tgt, j, "target"
                break
        if exit_px is None:
            j = min(i + tstop, len(df) - 1)
            exit_px, exit_i, reason = df.Open.iloc[j], j, "time"
        gross = exit_px / entry - 1
        net = gross - 0.30 / 100
        r_mult = net / ((entry - stop) / entry) if entry > stop else np.nan
        rows.append({
            "entry_date": dates[i + 1], "exit_date": dates[exit_i],
            "ticker": df.attrs.get("ticker", ""), "kind": "sympathy",
            "entry": round(entry, 2), "exit": round(exit_px, 2),
            "ret_pct": round(net * 100, 2), "r": round(r_mult, 2),
            "hold_days": int(exit_i - (i + 1)) + 1, "reason": reason,
        })
    return rows


def main() -> None:
    universe = get_universe()
    data, _ = load_data()
    smap = get_sector_map(universe)
    n_sec = smap.sector.nunique()
    n_leaders = smap.reset_index().sort_values(
        "market_cap_basic", ascending=False).groupby("sector").head(1).shape[0]
    print(f"universe={len(data)} symbols, {n_sec} sectors, {n_leaders} leaders")

    sig = build_signals(data, smap)
    print(f"sympathy signals: {len(sig)} ({sig.symbol.nunique()} symbols)")
    if sig.empty:
        return

    all_trades = []
    for sym, grp in sig.groupby("symbol"):
        df = data.get(sym)
        if df is None:
            continue
        idx = pd.DatetimeIndex([d for d in grp.date if d in df.index])
        all_trades += simulate_sympathy(df, idx)
    tr = pd.DataFrame(all_trades)
    if tr.empty:
        print("no trades simulated")
        return
    tr["entry_date"] = pd.to_datetime(tr.entry_date)
    s = stats(tr)
    print(f"\nTIER-II SYMPATHY (long laggard after leader pop)")
    print(f"  n={s['trades']} win={s['win_pct']}% avg={s['avg_ret_pct']}% "
          f"R={s['avg_r']} PF={s['profit_factor']} hold={s['median_hold_d']}d "
          f"maxDD={s['max_dd_eq_curve']}% trades/yr={s['trades_per_year']}")
    print("  exits:", dict(tr.reason.value_counts()))

    # regime split using Nifty trend
    nifty = _cached("NIFTY")
    ntrend = (nifty.Close > nifty.Close.rolling(200).mean()).fillna(False)
    ntrend.index = ntrend.index.tz_localize(None)
    mask = tr.entry_date.map(lambda d: bool(ntrend.asof(d)))
    for lbl, seg in [("in NIFTY uptrend", tr[mask]), ("in NIFTY downtrend", tr[~mask])]:
        ss = stats(seg)
        if ss.get("trades"):
            print(f"  {lbl:<18} n={ss['trades']:>4} win={ss['win_pct']}% "
                  f"avg={ss['avg_ret_pct']}% PF={ss['profit_factor']}")


if __name__ == "__main__":
    main()
