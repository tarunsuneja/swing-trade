"""Parameter fragility sweep + Monte Carlo on the adopted pullback book.

Part 1 FRAGILITY (approved Aug 21): one-at-a-time sweeps of the four pullback
exit knobs around validated defaults (stop buffer 0.25xATR, 5-bar low
lookback, 2R target, 20d time stop). Exit engine is a numpy port of
strategy_validation.simulate()'s pullback branch; at defaults it MUST
reproduce the published anchor (n=28630, PF=1.34, gated CAGR 13.7%) before
any sweep runs. Reported for the full signal set AND the traded RS>=90 book.

Robust = flat plateau around defaults. Knife-edge = neighbouring values
collapse -> parameter was overfit.

Part 2 MONTE CARLO (approved Aug 21): bootstrap the ACTUAL taken sequence
(RS>=90-gated, regime-gated, 6-slot portfolio engine, ~1,294 trades):
  - iid resample + circular block bootstrap (block=20 trades)
  - metrics: terminal multiple, CAGR, maxDD, worst trailing-12m, longest
    losing streak -> 5/25/50/75/95 percentiles
  - 12-month forward projection: 68-trade years drawn from the taken pool,
    P(negative year)

Run:  py -X utf8 test_fragility_mc.py      (~5-10 min)
"""
import numpy as np
import pandas as pd

from strategy_validation import (
    COST_PCT,
    MAX_SLOTS,
    get_universe,
    load_data,
    portfolio_cagr,
    signals,
    stats,
)

N_PATHS = 2000
BLOCK = 20
FWD_TRADES = 68  # ~taken rate per year (1294 / 19y)


# ---------------- numpy port of the pullback exit engine ----------------
def sim_pullback(o, h, l, atr, dates, sig_i, tk,
                 stop_buf=0.25, stop_lb=5, tgt_r=2.0, tstop=20):
    rows = []
    n = len(dates)
    for i in sig_i:
        if i + 1 >= n:
            continue
        entry = o[i + 1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        lo = l[max(0, i - stop_lb + 1):i + 1].min()
        stop = min(lo, entry - 2 * a) - stop_buf * a
        tgt = entry + tgt_r * (entry - stop)
        exit_px = exit_i = None
        for j in range(i + 1, min(i + 1 + tstop, n)):
            if l[j] <= stop:
                exit_px, exit_i = stop, j
                break
            if h[j] >= tgt:
                exit_px, exit_i = tgt, j
                break
        if exit_px is None:
            j = min(i + tstop, n - 1)
            exit_px, exit_i = o[j], j
        net = (exit_px / entry - 1) - COST_PCT / 100
        risk = (entry - stop) / entry
        rows.append({"ticker": tk, "entry_date": dates[i + 1],
                     "exit_date": dates[exit_i],
                     "ret_pct": round(net * 100, 2),
                     "r": round(net / risk, 2) if risk > 0 else np.nan,
                     "hold_days": int(exit_i - (i + 1)) + 1})
    return rows


def load_bundles():
    universe = get_universe()
    data, nifty = load_data()
    trend = (nifty["Close"] > nifty["Close"].rolling(200).mean()).fillna(False)
    trend.index = trend.index.tz_localize(None)
    bundles = []
    for tk, df in data.items():
        df.attrs["ticker"] = tk
        sigs = signals(df)["pullback"]
        if len(sigs) == 0:
            continue
        idx = np.array([df.index.searchsorted(d) for d in sigs])
        bundles.append((tk, df["Open"].to_numpy(float),
                        df["High"].to_numpy(float), df["Low"].to_numpy(float),
                        df["ATR"].to_numpy(float), df.index, idx))
    closes = {tk: d["Close"] for tk, d in data.items()
              if d is not None and len(d) >= 300}
    px = pd.DataFrame(closes)
    rs_panel = ((px / px.shift(252) - 1).rank(axis=1, pct=True) * 99)
    return bundles, rs_panel, trend


def run_config(bundles, rs_panel, **kw):
    rows = []
    for tk, o, h, l, atr, dates, idx in bundles:
        rows += sim_pullback(o, h, l, atr, dates, idx, tk, **kw)
    tr = pd.DataFrame(rows)
    tr["rs90"] = [
        bool(tk in rs_panel.columns and e in rs_panel.index
             and rs_panel.at[e, tk] >= 90)
        for tk, e in zip(tr["ticker"], tr["entry_date"])]
    return tr


def brief(tr, trend, label):
    s = stats(tr)
    if not s.get("trades"):
        print(f"  {label:<28} no trades")
        return
    p = portfolio_cagr(tr, trend)
    pg = (f"CAGR={p['cagr_pct']:>5}% DD={p['max_dd_pct']:>6}% took={p['taken']}"
          if p else "no portfolio")
    print(f"  {label:<28} n={s['trades']:>5} win={s['win_pct']:>5}% "
          f"avg={s['avg_ret_pct']:>+6}% PF={s['profit_factor']:>5} "
          f"| {pg}")


def fragility(bundles, rs_panel, trend):
    print("=" * 104)
    print("PART 1 - PARAMETER FRAGILITY (pullback exits; anchor must match "
          "n=28630 PF=1.34 CAGR=13.7%)")
    print("=" * 104)
    configs = [
        ("BASE buf.25 lb5 2R ts20", {}),
        ("stop_buf=0", dict(stop_buf=0.0)),
        ("stop_buf=0.125", dict(stop_buf=0.125)),
        ("stop_buf=0.375", dict(stop_buf=0.375)),
        ("stop_buf=0.50", dict(stop_buf=0.5)),
        ("target=1.5R", dict(tgt_r=1.5)),
        ("target=1.75R", dict(tgt_r=1.75)),
        ("target=2.5R", dict(tgt_r=2.5)),
        ("target=3.0R", dict(tgt_r=3.0)),
        ("tstop=10d", dict(tstop=10)),
        ("tstop=15d", dict(tstop=15)),
        ("tstop=30d", dict(tstop=30)),
    ]
    results = {}
    for ci, (label, kw) in enumerate(configs):
        tr = run_config(bundles, rs_panel, **kw)
        if ci == 0:
            s = stats(tr)
            ok = (s["trades"] == 28630 and abs(s["profit_factor"] - 1.34) < 0.01
                  and s["avg_ret_pct"] == 1.02)
            print(f"anchor check: n={s['trades']} PF={s['profit_factor']} "
                  f"avg={s['avg_ret_pct']} -> {'OK' if ok else 'MISMATCH - ABORT'}")
            if not ok:
                raise SystemExit(1)
        print(f"[{label}]")
        brief(tr, trend, "full:")
        brief(tr[tr["rs90"]], trend, "RS>=90:")
        results[label] = tr
    return results


# ---------------- Monte Carlo ----------------
def take_sequence(tr, trend):
    """Replicates portfolio_cagr() slotting, records the taken trades."""
    trades = tr.sort_values("entry_date")
    active, taken = [], []
    for _, t in trades.iterrows():
        if not bool(trend.asof(t.entry_date)):
            continue
        active = [a for a in active if a > t.entry_date]
        if len(active) >= MAX_SLOTS:
            continue
        active.append(t.exit_date)
        taken.append((t.exit_date, t.ret_pct))
    return pd.DataFrame(taken, columns=["exit_date", "ret_pct"])


def max_streak(losses):
    best = cur = 0
    for x in losses:
        cur = cur + 1 if x else 0
        best = max(best, cur)
    return best


def monte_carlo(taken):
    print("\n" + "=" * 104)
    print(f"PART 2 - MONTE CARLO on taken sequence (n={len(taken)}, "
          f"{N_PATHS} paths, block={BLOCK})")
    print("=" * 104)
    rets = taken["ret_pct"].to_numpy(float) / 100
    dates = pd.DatetimeIndex(taken["exit_date"])
    logr = np.log1p(rets / MAX_SLOTS)
    n = len(rets)
    yrs = max((dates[-1] - dates[0]).days / 365.25, 1.0)
    k = np.array([int(((dates > d - pd.Timedelta(days=365))
                       & (dates <= d)).sum()) for d in dates])

    rng = np.random.default_rng(42)

    def draw(kind):
        if kind == "iid":
            return rng.integers(0, n, n)
        starts = rng.integers(0, n, n // BLOCK + 1)
        idx = np.concatenate([(starts + b) % n for b in range(BLOCK)])[:n]
        return idx

    def path_metrics(idx):
        lr = logr[idx]
        eq = np.exp(np.cumsum(lr))
        dd = float((eq / np.maximum.accumulate(eq) - 1).min())
        s = np.cumsum(lr)
        w12 = 0.0
        for t in range(n):
            kk = int(k[min(t, n - 1)])
            if kk and t >= kk:
                w12 = min(w12, float(np.exp(s[t] - s[t - kk]) - 1))
        return (eq[-1], eq[-1] ** (1 / yrs) - 1, dd, w12,
                max_streak(rets[idx] <= 0))

    out = {k2: [] for k2 in ("term", "cagr", "dd", "w12", "streak")}
    for _ in range(N_PATHS):
        for kind in ("iid", "block"):
            m = path_metrics(draw(kind))
            for key, val in zip(out, m):
                out[key].append((kind, val))

    eq_real = np.exp(np.cumsum(logr))
    dd_real = float((eq_real / np.maximum.accumulate(eq_real) - 1).min())
    print(f"realized : term={eq_real[-1]:.1f}x CAGR={100 * (eq_real[-1] ** (1 / yrs) - 1):.1f}% "
          f"maxDD={100 * dd_real:.1f}% streak={max_streak(rets <= 0)}")
    hdr = f"{'metric':<16}" + "".join(f"{p:>14}" for p in ("5%", "25%", "50%", "75%", "95%"))
    for kind in ("iid", "block"):
        print(f"-- {kind} --")
        print(hdr)
        for name, key, fmt, scale in (("terminal", "term", "{:.1f}x", 1),
                                      ("CAGR %", "cagr", "{:+.1f}", 100),
                                      ("maxDD %", "dd", "{:.1f}", 100),
                                      ("worst 12m %", "w12", "{:+.1f}", 100),
                                      ("lose streak", "streak", "{:.0f}", 1)):
            vals = np.array([v for k2, v in out[key] if k2 == kind]) * scale
            ps = np.percentile(vals, [5, 25, 50, 75, 95])
            print(f"{name:<16}" + "".join(f"{fmt.format(x):>14}" for x in ps))

    fwd = rng.choice(rets, N_PATHS * FWD_TRADES).reshape(N_PATHS, FWD_TRADES)
    term12 = np.prod(1 + fwd / MAX_SLOTS, axis=1) - 1
    ps = np.percentile(term12 * 100, [5, 25, 50, 75, 95])
    print("\nforward 12m (68-trade year, iid from taken pool):")
    print(f"{'return %':<16}" + "".join(f"{x:>14.1f}" for x in ps))
    print(f"P(negative year) = {100 * float((term12 < 0).mean()):.1f}%")


def main():
    bundles, rs_panel, trend = load_bundles()
    results = fragility(bundles, rs_panel, trend)
    base = results["BASE buf.25 lb5 2R ts20"]
    taken = take_sequence(base[base["rs90"]], trend)
    print(f"\ntaken sequence for MC: {len(taken)} trades")
    monte_carlo(taken)


if __name__ == "__main__":
    main()
