"""Rebuild _price_cache/sectors.csv from yfinance (TV screener outage).

Writes sectors_yf.csv first; only after >=90% coverage succeeds does it
replace sectors.csv. Columns kept identical to the TradingView original
(symbol, sector, market_cap_basic) so get_sector_map() needs no changes.
"""
import os
import time

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "_price_cache")
UNIVERSE_FP = os.path.join(CACHE, "universe.txt")
OUT_FP = os.path.join(CACHE, "sectors_yf.csv")
FINAL_FP = os.path.join(CACHE, "sectors.csv")

with open(UNIVERSE_FP) as f:
    syms = [ln.strip() for ln in f if ln.strip()]

rows, failed = [], []
for k, sym in enumerate(syms):
    got = None
    for attempt in range(2):
        try:
            info = yf.Ticker(f"{sym}.NS").info
            sec, mc = info.get("sector"), info.get("marketCap")
            if sec:
                got = (sym, sec, mc)
                break
        except Exception:
            pass
        time.sleep(1.5)
    if got:
        rows.append(got)
    else:
        failed.append(sym)
    if (k + 1) % 25 == 0:
        print(f"  {k + 1}/{len(syms)} ok={len(rows)} fail={len(failed)}")
    time.sleep(0.4)

df = pd.DataFrame(rows, columns=["symbol", "sector", "market_cap_basic"])
df.to_csv(OUT_FP, index=False)
print(f"\ncovered {len(df)}/{len(syms)} ({df.sector.nunique()} sectors)")
if failed:
    print("failed:", ", ".join(failed))
if len(df) >= 0.9 * len(syms):
    df.to_csv(FINAL_FP, index=False)
    print("sectors.csv REPLACED")
else:
    print("coverage too low - sectors.csv left untouched")
