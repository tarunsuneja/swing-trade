#!/usr/bin/env python3
r"""Find live setups using ONLY the validated rules (strategy_validation.py).

Signals detected on cached daily data (top-150 universe, refreshed via
tv_history when stale):
  PULLBACK     uptrend (close>SMA200 rising, close>SMA50), dipped to SMA20
               within 5d, today reclaimed prior high -> enter next session
  BB_REVERSION RSI<35, close>SMA200, close<=lower BB(20,2)
  TIER2        sector leader popped >=5% on 2x volume, same-sector mate
               (corr>=0.55/120d, still lagging) catches up -> enter next
               session. Validated: n=66 PF=1.61 overall, PF=2.02 in Nifty
               uptrend, 0.66 in downtrend -> gate applies. Exits: 2R/10d.

Regime gate: no new longs unless Nifty > its 200-day SMA.

RS quality gate (adopted Aug 21 2026, see doc section 16 /
test_momentum_filters.py): PULLBACK entries additionally require an
O'Neil-style RS rating >= 90 (trailing 12-month return ranked vs this
universe). Validated: gated CAGR 13.7% -> 30.6%, uptrend-regime trade
PF 1.38 -> 1.62, stable across 2010-17 / 2018-26 eras. BB_REV/TIER2
rows carry RS info-only.

Sizing: Rs.6,00,000 satellite, 1.5% risk/trade (Rs.9,000), max notional
Rs.1,50,000 per position, 6 slots total (open positions subtracted manually).

Run:  py find_setups.py
Out:  console table + setups_YYYY-MM-DD.csv + signal_log.csv (idempotent
      audit trail: armed / RS-suppressed setups + daily gate state)
"""

import glob
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "_price_cache")
CAPITAL = 600_000
RISK_PCT = 0.015
MAX_NOTIONAL = 150_000
LOG_FP = os.path.join(HERE, "signal_log.csv")
LOG_COLS = ["logged_at", "signal_date", "ticker", "setup", "action",
            "entry_zone", "stop", "target_2R", "qty", "notional", "rs",
            "max_chase", "gate"]


def wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    out = df.copy()
    out["SMA20"] = c.rolling(20).mean()
    out["SMA50"] = c.rolling(50).mean()
    out["SMA200"] = c.rolling(200).mean()
    out["SMA200_20"] = out["SMA200"].shift(20)
    d = c.diff()
    out["RSI"] = 100 - 100 / (1 + wilder(d.clip(lower=0), 14)
                              / (-wilder(d.clip(upper=0), 14)))
    mid = c.rolling(20).mean()
    sd = c.rolling(20).std(ddof=0)
    out["BB_LO"] = mid - 2 * sd
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    out["ATR"] = wilder(tr, 14)
    return out


def regime_ok() -> tuple[bool, float]:
    fp = os.path.join(CACHE, "NIFTY.csv")
    df = pd.read_csv(fp, parse_dates=["date"], index_col="date")
    sma200 = df["Close"].rolling(200).mean().iloc[-1]
    last = float(df["Close"].iloc[-1])
    return last > sma200, round(last, 1)


def mk_row(kind, sym, sig_date, entry, stop, qty, rs_now, rsi_now,
           tgt_mid="", gate="", action="", max_chase="", age=0):
    risk_ps = entry - stop
    return {
        "setup": kind, "ticker": sym, "signal_date": sig_date,
        "age": age,
        "entry_zone": round(entry, 1), "stop": round(stop, 1),
        "target_2R": round(entry + 2 * risk_ps, 1), "target_mid": tgt_mid,
        "risk_per_sh": round(risk_ps, 1), "qty": qty,
        "notional": int(qty * entry),
        "rs": int(rs_now) if np.isfinite(rs_now) else "",
        "rsi": round(float(rsi_now), 1),
        "max_chase": max_chase,
        "gate": gate, "action": action,
        "logged_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }


def chase_cap(entry: float, atr: float) -> float:
    """H9: highest price payable next session - skip fills above this."""
    return round(entry * (1 + 0.5 * atr / entry), 1)


def log_signals(entries: list[dict], ok: bool) -> None:
    """Idempotent append of every armed/suppressed setup + gate state."""
    migrate_log()
    today = str(pd.Timestamp.now().date())
    now = pd.Timestamp.now().isoformat(timespec="seconds")
    recs = [{"logged_at": now, "signal_date": e["signal_date"],
             "ticker": e["ticker"], "setup": e["setup"].split("(")[0],
             "age": e.get("age", ""),
             "action": e["action"], "entry_zone": e["entry_zone"],
             "stop": e["stop"], "target_2R": e["target_2R"], "qty": e["qty"],
             "notional": e["notional"], "rs": e["rs"],
             "max_chase": e.get("max_chase", ""),
             "gate": e["gate"]}
            for e in entries]
    have = set()
    if os.path.exists(LOG_FP):
        try:
            old = pd.read_csv(LOG_FP, dtype=str)
            have = set(zip(old["signal_date"], old["ticker"], old["setup"]))
        except Exception:
            have = set()
    fresh = [r for r in recs
             if (str(r["signal_date"]), str(r["ticker"]), str(r["setup"]))
             not in have]
    if (today, "-", "GATE") not in have:
        fresh.append({"logged_at": now, "signal_date": today, "ticker": "-",
                      "setup": "GATE", "age": "",
                      "action": "OPEN" if ok else "CLOSED",
                      "entry_zone": "", "stop": "", "target_2R": "",
                      "qty": "", "notional": "", "rs": "",
                      "gate": "OPEN" if ok else "CLOSED"})
    if not fresh:
        print("(signal_log.csv: up to date)")
        return
    pd.DataFrame(fresh, columns=LOG_COLS).to_csv(
        LOG_FP, mode="a", header=not os.path.exists(LOG_FP), index=False)
    print(f"(signal_log.csv: appended {len(fresh)} row(s))")


def migrate_log() -> None:
    """One-time: add 'age' column to an existing signal_log.csv."""
    if not os.path.exists(LOG_FP):
        return
    try:
        head = pd.read_csv(LOG_FP, nrows=0)
        if "age" not in head.columns:
            old = pd.read_csv(LOG_FP, dtype=str)
            old.reindex(columns=LOG_COLS).to_csv(LOG_FP, index=False)
    except Exception:
        pass


def main() -> None:
    ok, nifty = regime_ok()
    print(f"Nifty {nifty:,} | regime gate: "
          f"{'OPEN - longs allowed' if ok else 'CLOSED - no new longs'}")

    rows = []
    raw = {}
    for fp in sorted(glob.glob(os.path.join(CACHE, "*.csv"))):
        sym = os.path.splitext(os.path.basename(fp))[0]
        if sym == "NIFTY" or sym.startswith("sectors"):
            continue
        df = pd.read_csv(fp, parse_dates=["date"], index_col="date")
        if len(df) < 300:
            continue
        raw[sym] = df

    # Cross-sectional RS rating (O'Neil-style): trailing 12-month return
    # ranked 1-99 vs this universe; PULLBACK entries require >= 90 (doc s16).
    px = pd.DataFrame({s: d["Close"] for s, d in raw.items()})
    rs_panel = ((px / px.shift(252) - 1).rank(axis=1, pct=True).mul(99)).iloc[-1]

    rs_suppressed = 0
    suppressed = []
    gate_txt = "OPEN" if ok else "CLOSED"
    # H12 signal freshness (doc s25): edge decays 100% -> 81% -> 71% -> 56%
    # entering 1/2/3/5 sessions after trigger. Signals expire after ONE
    # session (i.e. actionable at trigger+1 and trigger+2 only); older
    # signals, target-filled or stop-broken setups are dropped.
    MAX_AGE = 1
    for sym, d0 in sorted(raw.items()):
        df = indicators(d0)
        c, h, l = df["Close"], df["High"], df["Low"]
        n = len(df)

        uptrend = (c > df["SMA200"]) & (df["SMA200"] > df["SMA200_20"]) & (c > df["SMA50"])
        dipped = (l <= df["SMA20"]).rolling(5).max().astype(bool)
        pb_series = uptrend & dipped & (c > h.shift(1)) & (c > df["SMA20"])
        bb_series = (df["RSI"] < 35) & (c > df["SMA200"]) & (c <= df["BB_LO"] * 1.02)

        sig_i, kind, age = None, None, None
        for a in range(MAX_AGE + 1):
            i = n - 1 - a
            if i < 260:
                break
            if bool(pb_series.iloc[i]):
                sig_i, kind, age = i, "PULLBACK", a
                break
            if bool(bb_series.iloc[i]):
                sig_i, kind, age = i, "BB_REV", a
                break
        if sig_i is None:
            continue
        r = df.iloc[sig_i]
        if not np.isfinite(r.get("SMA200", np.nan)) or r["ATR"] <= 0:
            continue

        entry_ref = float(c.iloc[sig_i])
        rs_now = float(rs_panel.get(sym, np.nan))
        if kind == "PULLBACK":
            stop = float(min(l.iloc[sig_i - 4:sig_i + 1].min(),
                             entry_ref - 2 * r["ATR"]) - 0.25 * r["ATR"])
        else:
            stop = float(entry_ref - 1.5 * r["ATR"])
        risk_ps = entry_ref - stop
        if risk_ps <= 0:
            continue

        # invalidation since trigger: target already tagged or stop broken
        tgt_chk = (entry_ref + 2 * risk_ps if kind == "PULLBACK"
                   else float(r["SMA20"]))
        post_h, post_l = h.iloc[sig_i + 1:], l.iloc[sig_i + 1:]
        if len(post_h) and ((post_h >= tgt_chk).any() or (post_l <= stop).any()):
            continue

        qty_risk = int(RISK_PCT * CAPITAL // risk_ps)
        qty_cap = int(MAX_NOTIONAL // entry_ref)
        qty = min(qty_risk, qty_cap)
        if kind == "PULLBACK" and not (np.isfinite(rs_now) and rs_now >= 90):
            rs_suppressed += 1
            suppressed.append(mk_row(kind, sym, df.index[sig_i].date(),
                                     entry_ref, stop, qty, rs_now, r["RSI"],
                                     gate=gate_txt, action="SUPPRESSED_RS",
                                     max_chase=chase_cap(entry_ref, r["ATR"]),
                                     age=age))
            continue
        rows.append(mk_row(kind, sym, df.index[sig_i].date(), entry_ref, stop,
                           qty, rs_now, r["RSI"],
                           tgt_mid=round(float(r["SMA20"]), 1)
                           if kind == "BB_REV" else "",
                           gate=gate_txt, action="ARMED" if ok else "WATCH",
                           max_chase=chase_cap(entry_ref, r["ATR"]), age=age))

    # ---- Scan E: Tier-II sympathy (validated separately, see
    # test_tier2_sympathy.py / doc section 13) ----
    seen = {r["ticker"] for r in rows}
    try:
        import test_tier2_sympathy as t2

        smap = t2.get_sector_map(list(raw))
        sig = t2.build_signals(raw, smap, last_only=True)
        for _, s in sig.iterrows():
            sym = s["symbol"]
            if sym in seen or sym not in raw:
                continue
            df = raw[sym]
            d = indicators(df)
            i = len(d) - 1
            r = d.iloc[i]
            if not np.isfinite(r.get("SMA200", np.nan)) or r["ATR"] <= 0:
                continue
            entry_ref = float(d["Close"].iloc[i])
            stop = float(min(d["Low"].iloc[i - 4:i + 1].min(),
                             entry_ref - 2 * r["ATR"]) - 0.25 * r["ATR"])
            risk_ps = entry_ref - stop
            if risk_ps <= 0:
                continue
            qty_risk = int(RISK_PCT * CAPITAL // risk_ps)
            qty_cap = int(MAX_NOTIONAL // entry_ref)
            qty = min(qty_risk, qty_cap)
            rows.append(mk_row(f"TIER2({s['leader']} +{s['leader_ret_pct']}%)",
                               sym, df.index[i].date(), entry_ref, stop, qty,
                               float(rs_panel[sym])
                               if sym in rs_panel.index
                               and np.isfinite(rs_panel[sym]) else np.nan,
                               r["RSI"], gate=gate_txt,
                               action="ARMED" if ok else "WATCH",
                               max_chase=chase_cap(entry_ref, r["ATR"]),
                               age=0))
    except Exception as e:  # sympathy scan must never kill the main scan
        print(f"(tier2 scan skipped: {e})")

    if rs_suppressed:
        print(f"(RS gate suppressed {rs_suppressed} PULLBACK setup(s) "
              f"below RS 90 - doc section 16)")

    log_signals(suppressed + rows, ok)

    if not rows:
        print("\nNo qualifying setups today.")
        return
    res = pd.DataFrame(rows).sort_values(["setup", "ticker"])
    print(res.to_string(index=False))
    out = os.path.join(HERE, f"setups_{pd.Timestamp.now().date()}.csv")
    res.to_csv(out, index=False)
    print(f"\nSaved: {out}")
    print("Execution: enter NEXT session near signal close (limit orders); "
          "SKIP the trade if next open < stop or > max_chase (H9 gap policy); "
          "stop-loss mandatory at fill; exits per validated rules "
          "(pullback/tier2: 2R, time stop 20d/10d; bb_rev: SMA20 or 8d).")
    print("Freshness (H12, doc s25): age 0 = fired on latest bar (full edge), "
          "age 1 = one session late (81% edge) - signals older than that "
          "(or target-filled / stop-broken since trigger) are auto-expired.")


if __name__ == "__main__":
    main()
