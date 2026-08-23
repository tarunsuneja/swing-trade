"""H1+H2: O'Neil RS-rating and Minervini Trend-Template filters on TREND PULLBACK.

Questions (book deep-dive, Aug 21 2026):
  H1: do pullback entries in recent market LEADERS outperform laggards?
      RS Rating = trailing 12-month return ranked 1-99 within the cached
      universe, evaluated on the signal day. Variants: RS>=70 / 80 / 90.
  H2: Minervini's 8-point Trend Template (Stage-2 confirmation):
      c>MA150>MA200, MA200 rising >=1 month, MA50>MA150 and >MA200,
      c>MA50, c>=1.30x 52w-low, c>=0.75x 52w-high, RS>=70.

Method: filters REMOVE signals, never move an entry -- so we simulate the
UNFILTERED validated pullback exactly once, record each signal-day's
filter values, and derive every variant from the identical trade list.
Same exits, costs, slot logic as strategy_validation.py.

Caveats: top-150 CURRENT members => survivorship bias; RS ranks computed
within this universe only (not whole NSE); results are upper bounds.

Run:  py test_momentum_filters.py
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


def build_rs(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Cross-sectional 1-99 RS rating panel: trailing 12-month return rank."""
    px = pd.DataFrame({t: df["Close"] for t, df in data.items()})
    ret12m = px / px.shift(252) - 1
    return ret12m.rank(axis=1, pct=True).mul(99).round(0)


def trend_template(df: pd.DataFrame, rs: pd.Series) -> pd.Series:
    """Minervini Stage-2 checklist, evaluated bar by bar (incl. RS>=70)."""
    c, h, l = df["Close"], df["High"], df["Low"]
    ma50 = df["SMA50"]
    ma150 = c.rolling(150).mean()
    ma200 = df["SMA200"]
    lo252 = l.rolling(252).min()
    hi252 = h.rolling(252).max()
    m = ((c > ma150) & (c > ma200)
         & (ma150 > ma200)
         & (ma200 > ma200.shift(21))
         & (ma50 > ma150) & (ma50 > ma200)
         & (c > ma50)
         & (c >= 1.30 * lo252)
         & (c >= 0.75 * hi252)
         & (rs >= 70))
    return m.fillna(False)


def main() -> None:
    universe = get_universe()
    data, nifty = load_data()
    nifty_trend = (nifty["Close"] > nifty["Close"].rolling(200).mean()).fillna(False)
    nifty_trend.index = nifty_trend.index.tz_localize(None)
    rs = build_rs(data)

    rows, flags, sig_count = [], {}, 0
    for tk in universe:
        df = data.get(tk)
        if df is None or len(df) < 300:
            continue
        df.attrs["ticker"] = tk
        sigs = signals(df)["pullback"]
        if len(sigs) == 0:
            continue
        sig_count += len(sigs)
        r_s = rs[tk].reindex(df.index) if tk in rs.columns else pd.Series(np.nan, index=df.index)
        tt = trend_template(df, r_s)
        rows += simulate(df, sigs, "pullback")
        for d in sigs:
            i = df.index.searchsorted(d)
            if i + 1 >= len(df):
                continue
            e = df["Open"].iloc[i + 1]
            if not np.isfinite(e) or e <= 0:
                continue
            flags[(tk, df.index[i + 1])] = (float(r_s.iloc[i]), bool(tt.iloc[i]))

    tr = pd.DataFrame(rows)
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["exit_date"] = pd.to_datetime(tr["exit_date"])
    fl = [flags.get((t, e), (np.nan, False)) for t, e in zip(tr["ticker"], tr["entry_date"])]
    tr["rs_sig"] = [f[0] for f in fl]
    tr["tt_sig"] = [f[1] for f in fl]

    passing = {
        "RS>=70": 100 * (tr["rs_sig"] >= 70).mean(),
        "RS>=80": 100 * (tr["rs_sig"] >= 80).mean(),
        "RS>=90": 100 * (tr["rs_sig"] >= 90).mean(),
        "template": 100 * tr["tt_sig"].mean(),
    }
    print(f"universe={len(universe)}  pullback signals={sig_count}  trades={len(tr)}")
    print("share of signals passing: "
          + ", ".join(f"{k}={v:.0f}%" for k, v in passing.items()))

    variants = [
        ("BASELINE pullback (validated)", pd.Series(True, index=tr.index)),
        ("H1a: RS >= 70", tr["rs_sig"] >= 70),
        ("H1b: RS >= 80", tr["rs_sig"] >= 80),
        ("H1c: RS >= 90", tr["rs_sig"] >= 90),
        ("H2 : trend template (RS>=70)", tr["tt_sig"]),
        ("H2+: template + RS>=85", tr["tt_sig"] & (tr["rs_sig"] >= 85)),
    ]

    for label, mask in variants:
        sub = tr[mask.fillna(False)]
        s_all = stats(sub)
        if not s_all.get("trades"):
            print(f"\n{label}: no trades")
            continue
        tmask = sub["entry_date"].map(lambda d: bool(nifty_trend.asof(d)))
        s_up, s_dn = stats(sub[tmask]), stats(sub[~tmask])
        p_u = portfolio_cagr(sub)
        p_g = portfolio_cagr(sub, nifty_trend)
        print(f"\n{label}")
        line = ("  {:22s} n={:>5}  win={:>6}%  avg={:>+7.2f}%  R={:>+5.2f}  "
                "PF={:>5}  hold={:>3}d  maxDD={:>6.1f}%")
        args = lambda s: (s["trades"], s["win_pct"], s["avg_ret_pct"], s["avg_r"],
                          s["profit_factor"], s["median_hold_d"], s["max_dd_eq_curve"])
        print(line.format("overall", *args(s_all)))
        for nm, s in (("in Nifty-uptrend", s_up), ("in Nifty-downtrend", s_dn)):
            if s.get("trades"):
                print(line.format(nm, *args(s)))
        for nm, m2 in (("era 2010-2017", sub[sub["exit_date"] < pd.Timestamp("2018-01-01")]),
                       ("era 2018-2026", sub[sub["exit_date"] >= pd.Timestamp("2018-01-01")])):
            s2 = stats(m2)
            if s2.get("trades"):
                print(line.format(nm, *args(s2)))
        for tag, p in (("ungated", p_u), ("GATED ", p_g)):
            if p:
                print(f"  portfolio {tag}       CAGR={p['cagr_pct']}%  "
                      f"final=Rs.{p['final_equity']:,}  maxDD={p['max_dd_pct']}%  "
                      f"(took {p['taken']}, regime-skip {p.get('skipped_regime', 0)})")


if __name__ == "__main__":
    main()
