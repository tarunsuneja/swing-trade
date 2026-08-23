#!/usr/bin/env python3
"""H13 - TIER2 sympathy on OFFICIAL NSE industry map (Phase-1 item #8).

The live scan still uses the coarse yfinance/GICS-style map (11 buckets)
that was a stopgap during the TV screener outage. sectors_nse.csv holds
the official NSE Industry classification (20 sectors, 500 symbols) built
in Phase 1.2 - but it lacks market caps, so it was never promoted.

This test:
 1. merges NSE sectors + yfinance market caps into the standard schema;
 2. shows how sector leaders change old -> new map;
 3. rebuilds TIER2 signals BOTH ways on identical price data and
    simulates with the existing engine (t2.simulate_sympathy);
 4. gate: the new map must not degrade the uptrend-gated edge
    (old baseline: PF 2.02 uptrend / 0.66 downtrend, n=66).

If it passes, sectors.csv gets promoted (same 3-column format, so
get_sector_map()/find_setups need no code change).
"""
import os

import numpy as np
import pandas as pd

import strategy_validation as sv
import test_tier2_sympathy as t2

CACHE = t2.CACHE_DIR


def load_maps(universe):
    nse = pd.read_csv(os.path.join(CACHE, "sectors_nse.csv"))
    yf_map = pd.read_csv(os.path.join(CACHE, "sectors.csv"))

    # same sanitised-ticker fix as promote_sectors.py
    rev = {"M_M": "M&M", "GVT_D": "GVT&D"}
    nse["symbol"] = nse["symbol"].replace(rev)

    sec_nse = dict(zip(nse["symbol"], nse["sector"]))
    out = []
    for _, r in yf_map.iterrows():
        sym = r["symbol"]
        out.append({"symbol": sym,
                    "sector": sec_nse.get(sym),
                    "market_cap_basic": r.get("market_cap_basic", np.nan)})
    new = pd.DataFrame(out)

    missing_sec = int(new["sector"].isna().sum())
    missing_mc = int(new["market_cap_basic"].isna().sum())
    # drop symbols with no NSE sector (delisted/renamed etc.) - they cannot
    # form pairs; report them
    dropped = sorted(new.loc[new["sector"].isna(), "symbol"].tolist())
    new = new.dropna(subset=["sector"])
    return (yf_map.set_index("symbol"), new.set_index("symbol"),
            missing_mc, dropped)


def leader_table(smap):
    return (smap.reset_index()
            .sort_values("market_cap_basic", ascending=False)
            .groupby("sector").head(1)
            .set_index("sector")["symbol"])


def run_variant(data, smap, label, ntrend):
    sig = t2.build_signals(data, smap)
    trades = []
    for sym, grp in sig.groupby("symbol"):
        df = data.get(sym)
        if df is None:
            continue
        idx = pd.DatetimeIndex([d for d in grp.date if d in df.index])
        trades += t2.simulate_sympathy(df, idx)
    tr = pd.DataFrame(trades)
    if tr.empty:
        print(f"{label}: NO TRADES")
        return None, None
    tr["entry_date"] = pd.to_datetime(tr.entry_date)
    s = sv.stats(tr)
    mask = tr.entry_date.map(lambda d: bool(ntrend.asof(d)))
    up, dn = tr[mask], tr[~mask]

    def seg(x):
        ss = sv.stats(x)
        return (f"n={ss['trades']:>3} win={ss['win_pct']:>5}% "
                f"avg={ss['avg_ret_pct']:>+6}% PF={ss['profit_factor']}") \
            if ss.get("trades") else "n=0"

    print(f"\n--- {label} ---")
    print(f"signals: {len(sig)} across {sig.symbol.nunique()} symbols")
    print(f"ALL      {seg(tr)}")
    print(f"uptrend  {seg(up)}")
    print(f"downtn   {seg(dn)}")
    print("exits:", dict(tr.reason.value_counts()))
    return sig, tr


def main():
    universe = sv.get_universe()
    data, _ = sv.load_data()
    syms = list(data)

    old_map, new_map, n_no_mc, dropped = load_maps(syms)
    print(f"universe loaded: {len(data)} | new map rows: {len(new_map)} "
          f"| missing mcap: {n_no_mc} | no NSE sector (dropped): {dropped}")

    lo, ln = leader_table(old_map), leader_table(new_map)
    changed = [(s, lo.get(s, "-"), ln[s]) for s in ln.index if lo.get(s) != ln[s]]
    gone = [s for s in lo.index if s not in ln.index]
    born = [s for s in ln.index if s not in lo.index]
    print(f"\nleaders changed: {len(changed)} | sectors lost: {gone} "
          f"| sectors added: {born}")
    for s, o, n_ in changed:
        print(f"  {s:<28} {o:>12} -> {n_}")

    nifty = sv._cached("NIFTY")
    ntrend = (nifty.Close > nifty.Close.rolling(200).mean()).fillna(False)
    ntrend.index = ntrend.index.tz_localize(None)

    sig_o, tr_o = run_variant(data, old_map, "OLD map (11 GICS-ish)", ntrend)
    sig_n, tr_n = run_variant(data, new_map, "NEW map (official NSE)", ntrend)

    if sig_o is not None and sig_n is not None:
        ko = set(zip(sig_o.symbol, sig_o.date))
        kn = set(zip(sig_n.symbol, sig_n.date))
        inter = len(ko & kn)
        print(f"\nsignal-set overlap: {inter} shared | "
              f"old-only {len(ko - kn)} | new-only {len(kn - ko)}")

    # promote?
    up_stats = sv.stats(tr_n[tr_n.entry_date.map(
        lambda d: bool(ntrend.asof(d)))]) if tr_n is not None else {}
    ok = (up_stats.get("trades", 0) >= 30
          and float(up_stats.get("profit_factor", 0)) >= 1.4)
    print(f"\nGATE (uptrend n>=30 and PF>=1.4): "
          f"{'PASS - promote sectors.csv' if ok else 'FAIL - keep old map'}")


if __name__ == "__main__":
    main()
