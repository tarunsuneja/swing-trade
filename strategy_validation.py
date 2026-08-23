#!/usr/bin/env python3
r"""Validate the four swing strategies from this folder on real NSE data.

Strategies tested (rules from the local docs):
  1. TREND PULLBACK   uptrend (close>SMA200 rising, close>SMA50), dip to SMA20,
                      entry on reclaim of prior high; stop below pullback low,
                      target 2R, time stop 20d
  2. BB REVERSION     close<=lower BB(20,2), RSI<35, close>SMA200, vol<SMA10(vol);
                      target middle band, stop 1.5xATR, time stop 8d
  3. 52W HIGH BRKOUT  close>=98% of prior 252d high, close>SMA200, RSI 60-75,
                      vol>1.2x SMA20(vol); stop 2xATR, target 3R, time stop 40d
  4. PEAD PROXY       gap>3% on 2x volume closing positive; entry next open,
                      hold 20d, stop at gap-day low

Simulation realism: entry at NEXT open after signal, exits checked intraday
(stop assumed first when both hit same bar), 0.30% round-trip costs,
portfolio overlay with 6 equal-weight slots and Rs.12L starting capital.

Known limitation: current NIFTY-50 membership => survivorship bias; treat
results as upper bounds. Regime split uses Nifty vs its own SMA200.

Run:  py strategy_validation.py          (needs internet for yfinance)
Out:  console report + strategy_validation.json
"""

import json
import os
import sys
import time

import numpy as np
import pandas as pd

from tv_history import tv_daily

START = "2009-07-01"
COST_PCT = 0.30
CAPITAL = 1_200_000
MAX_SLOTS = 6


def get_universe(n: int = 150) -> list[str]:
    """Top-N NSE stocks by market cap (~NIFTY 200 head), cached on disk."""
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_price_cache")
    fp = os.path.join(cache_dir, "universe.txt")
    if os.path.exists(fp):
        syms = [s.strip() for s in open(fp, encoding="utf-8") if s.strip()]
        if len(syms) >= n - 20:
            return syms
    from tradingview_screener import Query, col
    _, df = (
        Query().set_markets("india").select("name")
        .where(col("type") == "stock", col("exchange") == "NSE",
               col("market_cap_basic") > 5e10)
        .order_by("market_cap_basic", ascending=False).limit(n)
        .get_scanner_data()
    )
    syms = sorted(df["name"].dropna().unique())
    os.makedirs(cache_dir, exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        f.write("\n".join(syms))
    return syms


def wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    df["SMA20"] = c.rolling(20).mean()
    df["SMA50"] = c.rolling(50).mean()
    df["SMA200"] = c.rolling(200).mean()
    df["SMA200_20ago"] = df["SMA200"].shift(20)
    delta = c.diff()
    df["RSI"] = 100 - 100 / (1 + wilder(delta.clip(lower=0), 14) / (-wilder(delta.clip(upper=0), 14)))
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std(ddof=0)
    df["BB_LO"], df["BB_MID"] = mid - 2 * sd, mid
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["ATR"] = wilder(tr, 14)
    df["VOL10"] = v.rolling(10).mean()
    df["VOL20"] = v.rolling(20).mean()
    df["HI252"] = h.rolling(252).max().shift(1)
    df["PREV_CLOSE"] = c.shift()
    df["PREV_HIGH"] = h.shift()
    return df


def _cached(symbol: str) -> pd.DataFrame | None:
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_price_cache")
    os.makedirs(cache, exist_ok=True)
    fp = os.path.join(cache, f"{symbol}.csv")
    if os.path.exists(fp):
        df = pd.read_csv(fp, parse_dates=["date"], index_col="date")
        if df.index[-1] >= pd.Timestamp.now().normalize() - pd.Timedelta(days=5):
            return df
    h = tv_daily(symbol, "NSE", n_bars=5000)
    if h is None or len(h) < 300:
        return None
    h.index = h.index.normalize()
    h.to_csv(fp)
    time.sleep(0.5)
    return h


def load_data() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    data = {}
    universe = get_universe(150)
    for t in universe:
        df = _cached(t)
        if df is not None:
            data[t] = add_indicators(df)
    nifty = _cached("NIFTY")
    if nifty is None:
        sys.exit("could not download NIFTY benchmark")
    print(f"loaded {len(data)}/{len(universe)} symbols "
          f"({nifty.index[-1].date()} latest)")
    return data, nifty


def signals(df: pd.DataFrame) -> dict[str, pd.DatetimeIndex]:
    c, o, h, l, v = df["Close"], df["Open"], df["High"], df["Low"], df["Volume"]
    uptrend = (c > df["SMA200"]) & (df["SMA200"] > df["SMA200_20ago"]) & (c > df["SMA50"])
    dipped = (l <= df["SMA20"]).rolling(5).max().astype(bool)
    reclaim = (c > df["PREV_HIGH"]) & (c > df["SMA20"])
    s_pullback = uptrend & dipped & reclaim & df["SMA200"].notna()

    s_bb = ((c <= df["BB_LO"]) & (df["RSI"] < 35) & (c > df["SMA200"])
            & (v < df["VOL10"]) & df["BB_LO"].notna())

    s_hi = ((c >= 0.98 * df["HI252"]) & (c > df["SMA200"])
            & (df["RSI"].between(60, 75)) & (v > 1.2 * df["VOL20"]) & df["HI252"].notna())

    gap = o / df["PREV_CLOSE"] - 1
    s_gap = ((gap > 0.03) & (v > 2 * df["VOL20"]) & (c > o)
             & df["PREV_CLOSE"].notna() & (df["VOL20"] > 0))

    out = {}
    for name, mask in [("pullback", s_pullback), ("bb_reversion", s_bb),
                       ("hi52", s_hi), ("pead", s_gap)]:
        idx = df.index[mask.fillna(False)]
        idx = idx[idx >= df.index[260]]
        out[name] = idx
    return out


def simulate(df: pd.DataFrame, sig_dates: pd.DatetimeIndex, kind: str) -> list[dict]:
    rows = []
    dates = df.index
    for d in sig_dates:
        i = dates.searchsorted(d)
        if i + 1 >= len(df):
            continue
        entry = df["Open"].iloc[i + 1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        atr = df["ATR"].iloc[i]
        if not np.isfinite(atr) or atr <= 0:
            continue
        if kind == "pullback":
            stop = min(df["Low"].iloc[i - 4:i + 1].min(), entry - 2 * atr) - 0.25 * atr
            tgt, tstop = entry + 2 * (entry - stop), 20
        elif kind == "bb_reversion":
            stop, tgt, tstop = entry - 1.5 * atr, df["BB_MID"].iloc[i], 8
        elif kind == "hi52":
            stop, tgt, tstop = entry - 2 * atr, None, 40
        else:
            stop, tgt, tstop = df["Low"].iloc[i], None, 20
        exit_px, exit_i, reason = None, None, ""
        hh = entry
        for j in range(i + 1, min(i + 1 + tstop, len(df))):
            lo, hi = df["Low"].iloc[j], df["High"].iloc[j]
            if kind == "hi52":
                hh = max(hh, hi)
                stop = max(stop, hh - 3 * atr)
            if lo <= stop:
                exit_px, exit_i, reason = stop, j, "stop"
                break
            if tgt is not None and hi >= tgt:
                exit_px, exit_i, reason = tgt, j, "target"
                break
            if kind == "bb_reversion" and df["Close"].iloc[j] >= df["BB_MID"].iloc[j]:
                exit_px, exit_i, reason = df["BB_MID"].iloc[j], j, "midband"
                break
        if exit_px is None:
            j = min(i + tstop, len(df) - 1)
            exit_px, exit_i, reason = df["Open"].iloc[j], j, "time"
        gross = exit_px / entry - 1
        net = gross - COST_PCT / 100
        r_mult = net / ((entry - stop) / entry) if entry > stop else np.nan
        rows.append({
            "entry_date": dates[i + 1], "exit_date": dates[exit_i],
            "ticker": df.attrs.get("ticker", ""), "kind": kind,
            "entry": round(entry, 2), "exit": round(exit_px, 2),
            "ret_pct": round(net * 100, 2), "r": round(r_mult, 2),
            "hold_days": int(exit_i - (i + 1)) + 1, "reason": reason,
        })
    return rows


def stats(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0}
    wins = trades[trades.ret_pct > 0]
    losses = trades[trades.ret_pct <= 0]
    gp, gl = wins.ret_pct.sum(), abs(losses.ret_pct.sum())
    eq = (1 + trades.set_index("exit_date").ret_pct / 100).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    yrs = max((trades.exit_date.max() - trades.entry_date.min()).days / 365.25, 0.25)
    return {
        "trades": int(len(trades)),
        "win_pct": round(100 * len(wins) / len(trades), 1),
        "avg_ret_pct": round(trades.ret_pct.mean(), 2),
        "avg_r": round(trades.r.mean(), 2),
        "profit_factor": round(gp / gl, 2) if gl > 0 else float("inf"),
        "median_hold_d": int(trades.hold_days.median()),
        "max_dd_eq_curve": round(float(dd) * 100, 1),
        "trades_per_year": round(len(trades) / yrs, 1),
    }


def portfolio_cagr(all_trades: pd.DataFrame, trend: pd.Series | None = None) -> dict:
    trades = all_trades.sort_values("entry_date")
    equity, curve, active = CAPITAL, [], []
    skipped_regime = 0
    for _, t in trades.iterrows():
        if trend is not None and not bool(trend.asof(t.entry_date)):
            skipped_regime += 1
            continue
        active = [a for a in active if a > t.entry_date]
        if len(active) >= MAX_SLOTS:
            continue
        active.append(t.exit_date)
        equity *= 1 + (t.ret_pct / 100) / MAX_SLOTS
        curve.append((t.exit_date, equity))
    if not curve:
        return {}
    ser = pd.Series({d: e for d, e in curve}).sort_index()
    yrs = (ser.index[-1] - ser.index[0]).days / 365.25
    cagr = (ser.iloc[-1] / CAPITAL) ** (1 / max(yrs, 0.25)) - 1
    dd = (ser / ser.cummax() - 1).min()
    return {"final_equity": round(float(ser.iloc[-1])), "cagr_pct": round(cagr * 100, 1),
            "max_dd_pct": round(float(dd) * 100, 1), "taken": int(len(curve)),
            "skipped_full": int(len(trades) - len(curve) - skipped_regime),
            "skipped_regime": int(skipped_regime)}


def main() -> None:
    data, nifty = load_data()
    nifty_trend = (nifty["Close"] > nifty["Close"].rolling(200).mean()).fillna(False)
    nifty_trend.index = nifty_trend.index.tz_localize(None)

    all_rows = []
    for tk, df in data.items():
        df.attrs["ticker"] = tk
        for kind, sigs in signals(df).items():
            all_rows.extend(simulate(df, sigs, kind))
    trades = pd.DataFrame(all_rows)
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    trades["exit_date"] = pd.to_datetime(trades["exit_date"])

    report, labels = {}, {
        "pullback": "1 TREND PULLBACK", "bb_reversion": "2 BB REVERSION",
        "hi52": "3 52W-HIGH BREAKOUT", "pead": "4 PEAD PROXY (gap>3%)",
    }
    bench = nifty["Close"].iloc[-1] / nifty["Close"].iloc[0]
    yrs = (nifty.index[-1] - nifty.index[0]).days / 365.25
    report["_benchmark_nifty_bh_cagr_pct"] = round((bench ** (1 / yrs) - 1) * 100, 1)

    for kind, label in labels.items():
        sub = trades[trades.kind == kind]
        overall = stats(sub)
        trend_mask = sub.entry_date.map(lambda d: bool(nifty_trend.asof(d)))
        rep = {"overall": overall,
               "in_uptrend_regime": stats(sub[trend_mask]),
               "in_downtrend_regime": stats(sub[~trend_mask]),
               "portfolio_6slot": portfolio_cagr(sub),
               "portfolio_6slot_regime_gated": portfolio_cagr(sub, nifty_trend)}
        report[label] = rep

        print(f"\n{'=' * 72}\n{label}\n{'=' * 72}")
        for seg in ("overall", "in_uptrend_regime", "in_downtrend_regime"):
            s = rep[seg]
            if s.get("trades"):
                print(f"  {seg:22s} n={s['trades']:5d}  win={s['win_pct']:5.1f}%  "
                      f"avg={s['avg_ret_pct']:+6.2f}%  R={s['avg_r']:+5.2f}  "
                      f"PF={s['profit_factor']:5.2f}  hold={s['median_hold_d']:3d}d  "
                      f"maxDD={s['max_dd_eq_curve']:6.1f}%")
            else:
                print(f"  {seg:22s} no trades")
        for key in ("portfolio_6slot", "portfolio_6slot_regime_gated"):
            p = rep[key]
            if p:
                tag = "gated" if "gated" in key else "ungated"
                print(f"  {'portfolio 6-slot ' + tag:22s} CAGR={p['cagr_pct']}%  "
                      f"final=Rs.{p['final_equity']:,}  maxDD={p['max_dd_pct']}%  "
                      f"(took {p['taken']}, regime-skip {p.get('skipped_regime', 0)}, "
                      f"full-skip {p['skipped_full']})")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "strategy_validation.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nSaved: {out}")
    print(f"Benchmark: Nifty buy&hold CAGR {report['_benchmark_nifty_bh_cagr_pct']}% "
          f"over {yrs:.1f}y | costs {COST_PCT}% RT | survivorship bias present")


if __name__ == "__main__":
    main()
