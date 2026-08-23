#!/usr/bin/env python3
r"""Satellite book tracker: journal review vs Nifty benchmark + kill switch.

Reads trade_journal.csv (same folder). Rules from the 2026 framework:
  - satellite capital assumed Rs.6,00,000
  - kill switch: rolling 6-month satellite return below Nifty's -> WARN;
    below it again next month -> STOP trading for the quarter

Run:  py satellite_tracker.py        (weekly or monthly, after market close)
Out:  console report + satellite_status.json
"""

import json
import os

import pandas as pd

from tv_history import tv_daily

CAPITAL = 600_000
HERE = os.path.dirname(os.path.abspath(__file__))
JOURNAL = os.path.join(HERE, "trade_journal.csv")
STATUS_OUT = os.path.join(HERE, "satellite_status.json")


def nifty_return_since(days: int) -> float | None:
    fp = os.path.join(HERE, "_price_cache", "NIFTY.csv")
    if os.path.exists(fp):
        df = pd.read_csv(fp, parse_dates=["date"], index_col="date")
    else:
        df = tv_daily("NIFTY", "NSE", n_bars=5000)
        if df is None:
            return None
    cut = df.index[-1] - pd.Timedelta(days=days)
    base = df.loc[df.index <= cut, "Close"]
    if base.empty:
        return None
    return float(df["Close"].iloc[-1] / base.iloc[-1] - 1)


def main() -> None:
    j = pd.read_csv(JOURNAL)
    j["exit_date"] = pd.to_datetime(j["exit_date"], errors="coerce")
    closed = j[j["exit_date"].notna()].copy()
    open_trades = j[j["exit_date"].isna()]

    print("=" * 66)
    print("SATELLITE BOOK REVIEW")
    print("=" * 66)

    open_risk = float((open_trades["entry"] - open_trades["stop"]).abs()
                      .mul(open_trades["qty"]).sum()) if len(open_trades) else 0.0
    print(f"Open positions : {len(open_trades)}   capital at risk: Rs.{open_risk:,.0f}")

    if closed.empty:
        print("\nNo closed trades yet - fill exit_date/exit_price in "
              "trade_journal.csv as trades close.")
    else:
        closed["pnl"] = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0)
        wins = (closed["r_multiple"] > 0).sum()
        span_days = (closed["exit_date"].max() - closed["entry_date"].min()).days or 1
        sat_ret = closed["pnl"].sum() / CAPITAL
        nifty_ret = nifty_return_since(span_days) or float("nan")
        print(f"Closed trades  : {len(closed)}   win rate: {100 * wins / len(closed):.0f}%"
              f"   avg R: {pd.to_numeric(closed['r_multiple'], errors='coerce').mean():+.2f}")
        print(f"Realized P&L   : Rs.{closed['pnl'].sum():,.0f}"
              f"  ({sat_ret * 100:+.1f}% on Rs.{CAPITAL:,})")
        print(f"Nifty same span: {nifty_ret * 100:+.1f}%")

        win6 = closed[closed["exit_date"] >= pd.Timestamp.now() - pd.Timedelta(days=183)]
        if len(win6) >= 3:
            sat6 = win6["pnl"].sum() / CAPITAL
            nifty6 = nifty_return_since(183) or float("nan")
            verdict = ("OK" if sat6 >= nifty6 else "WARN - halve position size")
            print(f"\nRolling 6M     : satellite {sat6 * 100:+.1f}% vs Nifty {nifty6 * 100:+.1f}%"
                  f"  -> {verdict}")
        else:
            print("\nRolling 6M     : insufficient closed trades (<3) for kill-switch check")

    status = {"open_positions": int(len(open_trades)),
              "closed_trades": int(len(closed)),
              "capital_at_risk": round(open_risk),
              "generated": str(pd.Timestamp.now().date())}
    with open(STATUS_OUT, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    print(f"\nSaved: {STATUS_OUT}")


if __name__ == "__main__":
    main()
