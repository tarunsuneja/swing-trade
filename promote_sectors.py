#!/usr/bin/env python3
"""Promote official NSE sectors to _price_cache/sectors.csv (H13, doc s26).

Builds the standard 3-column schema (symbol, sector, market_cap_basic):
sector <- sectors_nse.csv (official NSE Industry, validated in
test_tier2_official.py), market cap <- existing yfinance map.
NSE export sanitises tickers ('M&M' -> 'M_M'), fixed via ALIAS.
Only overwrites sectors.csv when coverage is complete enough;
sectors_yf.csv remains the untouched raw fallback.
"""
import os
import shutil

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "_price_cache")
UNIVERSE_FP = os.path.join(CACHE, "universe.txt")

ALIAS = {"M&M": "M_M", "GVT&D": "GVT_D"}  # universe ticker -> NSE ticker

nse = pd.read_csv(os.path.join(CACHE, "sectors_nse.csv"))
yf = pd.read_csv(os.path.join(CACHE, "sectors.csv"))

rev_alias = {v: k for k, v in ALIAS.items()}
nse["symbol"] = nse["symbol"].replace(rev_alias)

mcap = dict(zip(yf["symbol"], yf["market_cap_basic"]))
merged = nse[nse["symbol"].isin(mcap)].copy()
merged["market_cap_basic"] = merged["symbol"].map(mcap)
merged = merged[["symbol", "sector", "market_cap_basic"]]

with open(UNIVERSE_FP) as f:
    uni = [ln.strip() for ln in f if ln.strip()]
have_cache = [s for s in uni if s in mcap]
covered = [s for s in have_cache if s in set(merged["symbol"])]
missing = sorted(set(have_cache) - set(merged["symbol"]))
print(f"tradable universe: {len(have_cache)} | covered by new map: "
      f"{len(covered)} | missing: {missing}")
print(f"sectors: {merged['sector'].nunique()}")

if len(covered) < 0.9 * len(have_cache) or merged["market_cap_basic"].isna().any():
    print("coverage too low - NOT promoting")
else:
    bak = os.path.join(CACHE, "sectors_gics_backup.csv")
    if not os.path.exists(bak):
        shutil.copyfile(os.path.join(CACHE, "sectors.csv"), bak)
    merged.to_csv(os.path.join(CACHE, "sectors.csv"), index=False)
    print("sectors.csv PROMOTED (old map backed up to sectors_gics_backup.csv)")
