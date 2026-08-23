#!/usr/bin/env python3
"""H10 - Portfolio-level concentration controls (Phase 1.2).

Baseline = the validated RS>=90 taken sequence (portfolio_cagr on the
anchor engine): CAGR 27.5%, DD -34.8%, 1,294 taken. Any constraint must
not degrade that materially; the prize is drawdown reduction.

Variants:
  - sector cap: at most N concurrent open positions from one sector
    (N=2 ~= user's 33% of slots; capital-weighted equivalent since the
     slot sim weights equally)
  - correlation priority: skip a candidate whose trailing-120d return
    correlation with ANY open position >= threshold
Sector source: NSE official Industry column (ind_nifty500list.csv),
fallback to existing TV screener map for names outside Nifty 500.
"""
import os
import urllib.request
import csv
import io

import numpy as np
import pandas as pd

from strategy_validation import CAPITAL, load_data, portfolio_cagr
from test_fragility_mc import load_bundles, run_config

HERE = os.path.dirname(os.path.abspath(__file__))
NSE_FP = os.path.join(HERE, "_price_cache", "sectors_nse.csv")
LIST_URL = ("https://archives.nseindia.com/content/indices/"
            "ind_nifty500list.csv")


def tv(sym: str) -> str:
    return sym.replace("-", "_").replace("&", "_").replace(".", "_")


def nse_industries() -> dict[str, str]:
    if os.path.exists(NSE_FP):
        df = pd.read_csv(NSE_FP)
        if len(df) > 400:
            return dict(zip(df["symbol"], df["sector"]))
    req = urllib.request.Request(
        LIST_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0)"})
    rows = list(csv.DictReader(io.StringIO(
        urllib.request.urlopen(req, timeout=30).read().decode("utf-8-sig"))))
    out = {tv(r["Symbol"].strip().upper()): r["Industry"].strip()
           for r in rows}
    pd.DataFrame({"symbol": out.keys(), "sector": out.values()}
                 ).to_csv(NSE_FP, index=False)
    print(f"NSE industry map cached: {len(out)} symbols")
    return out


def build_sector_map(universe: list[str]) -> dict[str, str]:
    m = nse_industries()
    fp = os.path.join(HERE, "_price_cache", "sectors.csv")
    legacy = {}
    if os.path.exists(fp):
        legacy = dict(zip(pd.read_csv(fp)["symbol"],
                          pd.read_csv(fp)["sector"]))
    out = {}
    for s in universe:
        sec = m.get(s) or legacy.get(s) or "UNKNOWN"
        out[s] = sec
    unk = [s for s, v in out.items() if v == "UNKNOWN"]
    print(f"sector map: {len(out)} symbols, "
          f"{len(set(out.values()))} sectors, unknown={len(unk)} {unk[:5]}")
    return out


def constrained_sim(trades: pd.DataFrame, trend: pd.Series,
                    sector: dict[str, str], rets: pd.DataFrame | None,
                    sec_max=None, corr_max=None, win=120,
                    return_taken=False):
    """portfolio_cagr clone with optional sector/correlation gates."""
    tr = trades.sort_values("entry_date")
    equity, curve, active = CAPITAL, [], []
    taken = []
    sk_regime = sk_slots = sk_sector = sk_corr = 0
    for _, t in tr.iterrows():
        d = t.entry_date
        if trend is not None and not bool(trend.asof(d)):
            sk_regime += 1
            continue
        active = [a for a in active if a["exit"] > d]
        if len(active) >= 6:
            sk_slots += 1
            continue
        sec = sector.get(t.ticker, "UNKNOWN")
        if sec_max is not None and sum(a["sec"] == sec for a in active) >= sec_max:
            sk_sector += 1
            continue
        if corr_max is not None and rets is not None and len(active):
            hist = rets.loc[rets.index <= d].tail(win)
            if len(hist) >= 60:
                blocked = False
                for a in active:
                    cols = [t.ticker, a["tk"]]
                    if all(c in hist.columns for c in cols):
                        c = hist[cols].corr().iloc[0, 1]
                        if np.isfinite(c) and c >= corr_max:
                            blocked = True
                            break
                if blocked:
                    sk_corr += 1
                    continue
        active.append({"exit": t.exit_date, "tk": t.ticker, "sec": sec})
        equity *= 1 + (t.ret_pct / 100) / 6
        curve.append((t.exit_date, equity))
        taken.append((t.exit_date, t.ret_pct))
    if not curve:
        out = {}
    else:
        ser = pd.Series({d: e for d, e in curve}).sort_index()
        yrs = (ser.index[-1] - ser.index[0]).days / 365.25
        out = {"cagr_pct": round(((ser.iloc[-1] / CAPITAL) ** (1 / max(yrs, 0.25)) - 1) * 100, 1),
               "max_dd_pct": round(float((ser / ser.cummax() - 1).min()) * 100, 1),
               "taken": len(curve), "skip_regime": sk_regime,
               "skip_full": sk_slots, "skip_sector": sk_sector,
               "skip_corr": sk_corr}
    if return_taken:
        return out, pd.DataFrame(taken, columns=["exit_date", "ret_pct"])
    return out


def mc_head_to_head(seq_a, seq_b, label_a="V0", label_b="V3",
                    n_paths=2000, block=20):
    """Bootstrap terminal-equity & maxDD bands for two taken sequences."""
    rng = np.random.default_rng(42)

    def bands(seq):
        rets = seq["ret_pct"].to_numpy(float) / 100
        logr = np.log1p(rets / 6)
        n = len(logr)
        res = {"term": [], "dd": []}
        for _ in range(n_paths):
            for kind in ("iid", "block"):
                if kind == "iid":
                    idx = rng.integers(0, n, n)
                else:
                    st = rng.integers(0, n, n // block + 1)
                    idx = np.concatenate([(st + b) % n
                                          for b in range(block)])[:n]
                lr = logr[idx]
                eq = np.exp(np.cumsum(lr))
                res["term"].append((kind, eq[-1]))
                res["dd"].append((kind, float(
                    (eq / np.maximum.accumulate(eq) - 1).min())))
        return res

    print("\n--- Monte Carlo head-to-head (2,000 paths each) ---")
    print(f"{'metric':<18}{label_a + ' p5/p50/p95':>26}"
          f"{label_b + ' p5/p50/p95':>26}")
    ba, bb = bands(seq_a), bands(seq_b)
    for metric, fmt in (("term", "{:.0f}x"), ("dd", "{:.0%}")):
        row = f"{metric:<18}"
        for band in (ba[metric], bb[metric]):
            vals = {}
            for kind in ("iid", "block"):
                v = sorted(x[1] for x in band if x[0] == kind)
                vals[kind] = tuple(fmt.format(v[i]) for i in (int(.05 * len(v)), len(v) // 2, int(.95 * len(v))))
            row += f" i:{vals['iid'][0]}/{vals['iid'][1]}/{vals['iid'][2]:<7}"
            row += f" b:{vals['block'][0]}/{vals['block'][1]}/{vals['block'][2]}"
        print(row)


def main():
    bundles, rs_panel, trend = load_bundles()
    tr = run_config(bundles, rs_panel)
    r90 = tr[tr["rs90"]].copy()

    # sanity: unconstrained sim must match published portfolio_cagr result
    base_pub = portfolio_cagr(r90, trend)
    print(f"published baseline: CAGR={base_pub['cagr_pct']}% "
          f"DD={base_pub['max_dd_pct']}% taken={base_pub['taken']}")

    universe = sorted({b[0] for b in bundles})
    sector = build_sector_map(universe)

    # returns panel for correlations
    data, _ = load_data()
    px = pd.DataFrame({tk: d["Close"] for tk, d in data.items()})
    rets = px.pct_change()

    variants = [
        ("V0 baseline (no constraint)", {}),
        ("V1 max 2 / sector", dict(sec_max=2)),
        ("V2 max 1 / sector", dict(sec_max=1)),
        ("V3 corr<0.80 vs open", dict(corr_max=0.80)),
        ("V4 corr<0.70 vs open", dict(corr_max=0.70)),
        ("V5 sec2 + corr 0.70", dict(sec_max=2, corr_max=0.70)),
    ]
    print("\n" + "=" * 100)
    print(f"H10 CONSTRAINTS on RS>=90 book "
          f"(target: DD down, CAGR within ~2pts of {base_pub['cagr_pct']}%)")
    print("=" * 100)
    seqs = {}
    for label, kw in variants:
        r, taken = constrained_sim(
            r90, trend, sector,
            None if kw.get("corr_max") is None else rets,
            return_taken=True, **kw)
        seqs[label.split()[0]] = taken
        print(f"{label:<28} CAGR={r['cagr_pct']:>5}% DD={r['max_dd_pct']:>6}% "
              f"taken={r['taken']:>4} | skip: sector={r['skip_sector']:>3} "
              f"corr={r['skip_corr']:>3}")

    mc_head_to_head(seqs["V0"], seqs["V3"])


if __name__ == "__main__":
    main()
