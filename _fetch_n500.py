#!/usr/bin/env python3
"""One-time (resumable) builder of the Nifty-500 SANDBOX cache.

- Sandbox dir: _price_cache_n500/  (live scanner keeps using _price_cache/)
- Copies all existing series from _price_cache/, then writes universe.txt
  with the full TV-mapped Nifty 500 list, then fetches any missing series
  from TradingView. Re-run safely: existing files are skipped.
"""
import os
import time
import urllib.request
import csv
import io

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "_price_cache")
DST = os.path.join(HERE, "_price_cache_n500")
NEW_FP = os.path.join(HERE, "_n500_new.txt")
LIST_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"


def tv(sym: str) -> str:
    return sym.replace("-", "_").replace("&", "_").replace(".", "_")


def nifty500() -> list[str]:
    req = urllib.request.Request(
        LIST_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    data = urllib.request.urlopen(req, timeout=30).read().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(data)))
    syms = sorted({tv(r["Symbol"].strip().upper()) for r in rows})
    return syms


def main():
    os.makedirs(DST, exist_ok=True)

    # 1) copy every cached series we already have
    copied = missing = 0
    for fn in os.listdir(SRC):
        if not fn.endswith(".csv"):
            continue
        src_fp, dst_fp = os.path.join(SRC, fn), os.path.join(DST, fn)
        if not os.path.exists(dst_fp):
            with open(src_fp, "rb") as a, open(dst_fp, "wb") as b:
                b.write(a.read())
            copied += 1
        else:
            missing += 1
    print(f"copied {copied} cached series ({missing} already present)")

    # 2) universe.txt = full mapped Nifty 500
    syms = nifty500()
    with open(os.path.join(DST, "universe.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(syms))
    print(f"universe.txt written: {len(syms)} symbols")

    # 3) fetch what's still missing (resumable)
    from tv_history import tv_daily
    todo = [s for s in syms if not os.path.exists(os.path.join(DST, f"{s}.csv"))]
    print(f"to fetch: {len(todo)}")
    fails = []
    t0 = time.time()
    for i, sym in enumerate(todo, 1):
        try:
            h = tv_daily(sym, "NSE", n_bars=5000)
            if h is None or len(h) < 300:
                fails.append(f"{sym}: short/none ({0 if h is None else len(h)})")
            else:
                h.index = h.index.normalize()
                h.to_csv(os.path.join(DST, f"{sym}.csv"))
        except Exception as e:
            fails.append(f"{sym}: {type(e).__name__}: {e}")
        if i % 25 == 0 or i == len(todo):
            el = time.time() - t0
            eta = el / i * (len(todo) - i)
            print(f"[{i}/{len(todo)}] elapsed {el:.0f}s eta {eta:.0f}s "
                  f"fails={len(fails)}", flush=True)
        time.sleep(0.3)
    if fails:
        fp = os.path.join(HERE, "_n500_fetch_fails.txt")
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n".join(fails))
        print(f"{len(fails)} failures -> {fp}")
        for x in fails[:15]:
            print("  " + x)
    have = sum(1 for s in syms if os.path.exists(os.path.join(DST, f"{s}.csv")))
    print(f"DONE: sandbox has {have}/{len(syms)} series")


if __name__ == "__main__":
    main()
