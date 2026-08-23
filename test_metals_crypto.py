"""Gold / Silver / Bitcoin: does our regime-gating approach work there?

Tests the simplest documented anomaly for these assets - TIME-SERIES
MOMENTUM / trend following (Moskowitz-Ooi-Pedersen 2012, AQR two-century
study): stay long while price > its 200-DMA, exit to cash otherwise.

Compared against each asset's buy-and-hold over identical windows.
Data: TradingView websocket (same tv_history.py pipeline).
"""
import sys

import numpy as np
import pandas as pd

from tv_history import tv_daily

SERIES = [
    ("GOLD  (USD spot)", "XAUUSD", "OANDA"),
    ("SILVER(USD spot)", "XAGUSD", "OANDA"),
    ("BITCOIN        ", "BTCUSD", "BITSTAMP"),
    ("NIFTY  (ref)   ", "NIFTY", "NSE"),
]


def fetch(sym: str, exch: str) -> pd.DataFrame | None:
    h = tv_daily(sym, exch, n_bars=5000)
    if h is None or len(h) < 300:
        return None
    h.index = h.index.normalize()
    return h


def evaluate(df: pd.DataFrame, label: str) -> None:
    c = df.Close.dropna()
    sma200 = c.rolling(200).mean()
    regime = (c > sma200).fillna(False)

    ret = c.pct_change().fillna(0)
    yrs = (c.index[-1] - c.index[0]).days / 365.25

    def perf(r: pd.Series, name: str, exposure: float | None = None) -> None:
        eq = (1 + r).cumprod()
        cagr = (eq.iloc[-1] ** (1 / yrs) - 1) * 100
        dd = (eq / eq.cummax() - 1).min() * 100
        vol = r.std() * np.sqrt(252) * 100
        sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0
        exp_txt = f"  exposure={exposure:.0%}" if exposure is not None else ""
        print(f"    {name:<16} CAGR={cagr:+7.2f}%  maxDD={dd:7.1f}%  "
              f"vol={vol:5.1f}%  Sharpe={sharpe:4.2f}{exp_txt}")

    print(f"\n{label}  [{c.index[0].date()} -> {c.index[-1].date()}]  "
          f"({len(c)} bars, {yrs:.1f}y)")
    perf(ret, "Buy & Hold")
    strat = ret.where(regime.shift(1).fillna(False), 0.0)
    perf(strat, "200DMA regime", float(regime.mean()))
    # rough cost estimate: ~2 round trips/year when regime flips x 0.05%
    flips = int((regime != regime.shift(1)).sum())
    strat_net = strat - (regime.astype(int).diff().abs().fillna(0)) * 0.0005
    perf(strat_net, "  net of costs")


def main() -> None:
    for label, sym, exch in SERIES:
        df = fetch(sym, exch)
        if df is None:
            print(f"\n{label}: data unavailable")
            continue
        evaluate(df, label)


if __name__ == "__main__":
    main()
