"""Test the book's RSIX confirmation idea vs our current BB_REV entry.

Book (McCall & Whistler, Ch 6): do not buy while RSI is falling into
oversold; wait for RSI to cross back UP through the threshold as
confirmation that a bottom formed. Our current BB_REV enters on the day
the close pierces the lower band with RSI < 35 (no confirmation).

Variants:
  A: book RSIX standalone - RSI(14) crosses back above 35 within 3 days
     of being below 30, trend context required.
  B: our exact BB_REV setup + book's confirmation filter - band-pierce
     signal day, but entry only after RSI crosses back above 35 within
     2 days; entry at next open after confirmation.
Both use the same exits as our validated bb_reversion (mid-band target /
8-day time stop / 1.5xATR stop).
"""
import pandas as pd

from strategy_validation import (
    add_indicators,
    get_universe,
    load_data,
    signals,
    simulate,
    stats,
    wilder,
)


def rsi_crossback_signals(df: pd.DataFrame) -> pd.DatetimeIndex:
    c = df.Close
    d = c.diff()
    rsi = 100 - 100 / (1 + wilder(d.clip(lower=0), 14) / (-wilder(d.clip(upper=0), 14)))
    sma200 = c.rolling(200).mean()
    liq = (c * df.Volume).rolling(50).mean() >= 5e7

    recent_os = (rsi < 30).rolling(3).max().astype(bool)
    cross_up = (rsi > 35) & (rsi.shift(1) <= 35)
    sig = cross_up & recent_os & (c > sma200) & (sma200 > sma200.shift(20)) & liq
    idx = df.index[sig.fillna(False)]
    return idx[idx >= df.index[260]]


def bb_rev_confirmed_signals(df: pd.DataFrame, max_wait: int = 2) -> pd.DatetimeIndex:
    """Our exact BB_REV setup + the book's confirmation filter."""
    base = signals(df)["bb_reversion"]
    confirmed = []
    for dt in base:
        i = df.index.get_loc(dt)
        w = slice(i + 1, i + 1 + max_wait)
        rsi_now, rsi_prev = df["RSI"].iloc[w], df["RSI"].shift(1).iloc[w]
        crossed = (rsi_now > 35) & (rsi_prev <= 35)
        if crossed.any():
            confirmed.append(df.index[i + 1 + int(crossed.values.argmax())])
    return pd.DatetimeIndex(confirmed)


def run(label: str, sig_fn) -> None:
    universe = get_universe()
    data, _ = load_data()
    rows = []
    for sym in universe:
        df = data.get(sym)
        if df is None or len(df) < 300:
            continue
        rows += simulate(df, sig_fn(df), "bb_reversion")
    s = stats(pd.DataFrame(rows))
    print(f"{label:<28} n={s['trades']:>5} win={s['win_pct']}% avg={s['avg_ret_pct']}% "
          f"R={s['avg_r']} PF={s['profit_factor']} hold={s['median_hold_d']}d")


def main() -> None:
    run("BASELINE our BB_REV", lambda df: signals(df)["bb_reversion"])
    run("A: book RSIX standalone", rsi_crossback_signals)
    run("B: our setup + RSIX wait", bb_rev_confirmed_signals)


if __name__ == "__main__":
    main()
