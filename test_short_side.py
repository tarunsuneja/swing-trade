"""Test MIRRORED (short-side) versions of our validated setups.

Motivation: our regime gate blocks longs while Nifty < 200-DMA. A working
short-side rule could harvest those periods instead. Academic warning:
equity short legs are historically weaker (Frazzini etc.) - test, don't assume.

Mirrors tested (entry next open after signal day, 0.30% RT costs):
  SHORT-PULLBACK : downtrend (close<SMA200 falling, <SMA50), rally touched
                   SMA20 within 5d, today failed back below prior low+SMA20
                   stop=max(5d high, e+2ATR)+0.25ATR, tgt=-2R, time 20d
  SHORT-BBREV    : RSI>65, close<SMA200, close>=BB_HI x0.98, vol<VOL10
                   stop=e+1.5ATR, tgt=midband, time 8d
  SHORT-TIER2    : leader drops <= -5% on 2x volume, correlated laggard
                   (120d corr>=0.55) hasn't caught up, laggard in downtrend
                   exits as SHORT-PULLBACK but time 10d
  SHORT-BREAKDOWN: close <= 1.02x LO252, close<SMA200, RSI 25-40,
                   vol>1.2xVOL20 - mirror of the rejected hi52 long
All intraday checks assume ADVERSE move first (conservative).
"""
import os

import numpy as np
import pandas as pd

from strategy_validation import (
    _cached,
    add_indicators,
    get_universe,
    load_data,
    stats,
)

COST = 0.30 / 100


def simulate_short(df: pd.DataFrame, sig_dates, style: str) -> list[dict]:
    rows = []
    dates = df.index
    for d in sig_dates:
        i = dates.searchsorted(d)
        if i + 1 >= len(df):
            continue
        entry = df["Open"].iloc[i + 1]
        atr = df["ATR"].iloc[i]
        if not np.isfinite(entry) or entry <= 0 or not np.isfinite(atr) or atr <= 0:
            continue
        if style == "pullback":
            stop = (max(df["High"].iloc[i - 4:i + 1].max(), entry + 2 * atr)
                    + 0.25 * atr)
            tgt, tstop = entry - 2 * (stop - entry), 20
        elif style == "bbrev":
            stop, tgt, tstop = entry + 1.5 * atr, df["BB_MID"].iloc[i], 8
        else:  # tier2
            stop = (max(df["High"].iloc[i - 4:i + 1].max(), entry + 2 * atr)
                    + 0.25 * atr)
            tgt, tstop = entry - 2 * (stop - entry), 10
        exit_px, exit_i, reason = None, None, ""
        for j in range(i + 1, min(i + 1 + tstop, len(df))):
            hi, lo = df["High"].iloc[j], df["Low"].iloc[j]
            if hi >= stop:                      # adverse first
                exit_px, exit_i, reason = stop, j, "stop"
                break
            if tgt is not None and lo <= tgt:
                exit_px, exit_i, reason = tgt, j, "target"
                break
            if style == "bbrev" and df["Close"].iloc[j] <= df["BB_MID"].iloc[j]:
                exit_px, exit_i, reason = df["BB_MID"].iloc[j], j, "midband"
                break
        if exit_px is None:
            j = min(i + tstop, len(df) - 1)
            exit_px, exit_i, reason = df["Open"].iloc[j], j, "time"
        gross = 1 - exit_px / entry
        net = gross - COST
        r_mult = net / ((stop - entry) / entry) if stop > entry else np.nan
        rows.append({
            "entry_date": dates[i + 1], "exit_date": dates[exit_i],
            "kind": style, "entry": round(entry, 2), "exit": round(exit_px, 2),
            "ret_pct": round(net * 100, 2), "r": round(r_mult, 2),
            "hold_days": int(exit_i - (i + 1)) + 1, "reason": reason,
        })
    return rows


def short_signals(df: pd.DataFrame, style: str) -> pd.DatetimeIndex:
    c, h, v = df["Close"], df["High"], df["Volume"]
    dn = ((c < df["SMA200"]) & (df["SMA200"] < df["SMA200_20ago"])
          & (c < df["SMA50"]))
    bb_hi = df["BB_MID"] + 2 * (df["Close"].rolling(20).std(ddof=0))
    lo252 = df["Low"].rolling(252).min().shift(1)
    prev_low = df["Low"].shift(1)
    if style == "pullback":
        rallied = (h >= df["SMA20"]).rolling(5).max().astype(bool)
        fail = (c < prev_low) & (c < df["SMA20"])
        sig = dn & rallied & fail & df["SMA200"].notna()
    elif style == "bbrev":
        sig = ((c >= bb_hi * 0.98) & (df["RSI"] > 65) & (c < df["SMA200"])
               & (v < df["VOL10"]) & bb_hi.notna())
    elif style == "breakdown":
        sig = ((c <= 1.02 * lo252) & (c < df["SMA200"])
               & df["RSI"].between(25, 40) & (v > 1.2 * df["VOL20"])
               & lo252.notna())
    idx = df.index[sig.fillna(False)]
    return idx[idx >= df.index[260]]


def main() -> None:
    universe = get_universe()
    data, _ = load_data()

    # ---- three indicator-based mirrors ----
    for style in ("pullback", "bbrev", "breakdown"):
        rows = []
        for sym in universe:
            df = data.get(sym)
            if df is None or len(df) < 300:
                continue
            rows += simulate_short(df, short_signals(df, style), style)
        tr = pd.DataFrame(rows)
        s = stats(tr)
        print(f"\nSHORT-{style.upper():<9} n={s['trades']:>5} win={s['win_pct']}% "
              f"avg={s['avg_ret_pct']}% R={s['avg_r']} PF={s['profit_factor']} "
              f"hold={s['median_hold_d']}d")
        nifty = _cached("NIFTY")
        ntrend = (nifty.Close > nifty.Close.rolling(200).mean()).fillna(False)
        ntrend.index = ntrend.index.tz_localize(None)
        mask = tr.entry_date.map(lambda d: bool(ntrend.asof(pd.Timestamp(d))))
        for lbl, seg in [("  in NIFTY UPTREND", tr[mask]),
                         ("  in NIFTY DOWNTREND", tr[~mask])]:
            ss = stats(seg)
            if ss.get("trades"):
                print(f"{lbl:<22} n={ss['trades']:>5} win={ss['win_pct']}% "
                      f"avg={ss['avg_ret_pct']}% PF={ss['profit_factor']}")

    # ---- SHORT-TIER2 (book's own example direction) ----
    import test_tier2_sympathy as t2

    smap = t2.get_sector_map(universe)
    leaders = (smap.reset_index().sort_values("market_cap_basic", ascending=False)
               .groupby("sector").head(1)["symbol"].tolist())
    sectors = smap["sector"].to_dict()
    rets = {s: df.Close.pct_change() for s, df in data.items()}
    R = pd.DataFrame(rets)
    rows = []
    for leader in leaders:
        sec = sectors.get(leader)
        mates = [s for s, x in sectors.items()
                 if x == sec and s != leader and s in R.columns]
        l_ret = R.get(leader)
        if not sec or l_ret is None or not mates:
            continue
        l_evt = (l_ret <= -0.05) & (data[leader].Volume > 2 * data[leader].Volume.rolling(20).mean()).reindex(R.index)
        evt_dates = R.index[l_evt.fillna(False)]
        for mate in mates:
            dm = data[mate]
            corr = R[mate].rolling(120).corr(l_ret)
            sma200 = dm.Close.rolling(200).mean()
            downtrend = ((dm.Close < sma200)
                         & (sma200 < sma200.shift(20))).reindex(R.index).fillna(False)
            liq = ((dm.Close * dm.Volume).rolling(50).mean() >= 5e7
                   ).reindex(R.index).fillna(False)
            for t in evt_dates:
                i = R.index.get_loc(t)
                if i < 130 or i + 1 >= len(R.index):
                    continue
                cr = corr.iloc[i]
                if not np.isfinite(cr) or cr < 0.55:
                    continue
                m_r = R[mate].iloc[i]
                if not np.isfinite(m_r) or m_r <= l_ret.iloc[i] / 2:
                    continue
                if not bool(downtrend.iloc[i]) or not bool(liq.iloc[i]):
                    continue
                rows += simulate_short(
                    add_indicators(data[mate]),
                    pd.DatetimeIndex([data[mate].index[
                        min(np.searchsorted(data[mate].index, R.index[i]), len(data[mate]) - 1)]]),
                    "tier2")
    tr = pd.DataFrame(rows)
    if not tr.empty:
        s = stats(tr)
        print(f"\nSHORT-TIER2     n={s['trades']:>5} win={s['win_pct']}% "
              f"avg={s['avg_ret_pct']}% R={s['avg_r']} PF={s['profit_factor']} "
              f"hold={s['median_hold_d']}d")


if __name__ == "__main__":
    main()
