#!/usr/bin/env python3
r"""Live web view of the validated scanner (find_setups.py).

Run:   py scan_web.py          -> http://localhost:8787 opens automatically
Stop:  Ctrl+C

- Browser page auto-reloads every 60s; data pipeline rescan interval is
  SCAN_WEB_INTERVAL seconds (default 900 = 15 min).
- When any cached series' last bar is older than today, a background pass
  refetches it from TradingView (EOD data typically appears by evening),
  at most once per hour.
- Renders: regime gate banner, armed setups, RS-suppressed setups, recent
  signal_log history, plus a Family Plan tab (CORRECTED_ALLOCATION_V4 tables).
  Read-only display of the SAME artifacts the CLI
  produces; no trading logic lives here.
"""
import glob
import html
import os
import sys
import threading
import time
import traceback
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pandas as pd

import find_setups
from tv_history import tv_daily

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "_price_cache")
LOG_FP = os.path.join(HERE, "scan_web.log")
PORT_BASE = 8787
PAGE_RELOAD_SECS = 60
INTERVAL = int(os.environ.get("SCAN_WEB_INTERVAL", "900"))

STATE = {}
FIRST = threading.Event()
_last_data_attempt = 0.0


def log(msg):
    line = f"[{pd.Timestamp.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FP, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def universe_list():
    fp = os.path.join(CACHE, "universe.txt")
    with open(fp) as f:
        return [ln.strip() for ln in f if ln.strip()]


def refresh_data():
    """Pull any symbol whose cached EOD predates today (mirrors _cached)."""
    global _last_data_attempt
    _last_data_attempt = time.time()
    today = pd.Timestamp.now().normalize()
    syms = ["NIFTY"] + universe_list()
    todo = []
    for tk in syms:
        fp = os.path.join(CACHE, f"{tk}.csv")
        try:
            if os.path.exists(fp):
                df = pd.read_csv(fp, usecols=["date"])
                if pd.to_datetime(df["date"]).max().normalize() >= today:
                    continue
        except Exception:
            pass
        todo.append(tk)
    if not todo:
        return
    log(f"refreshing {len(todo)} stale series ...")
    for tk in todo:
        try:
            h = tv_daily(tk, "NSE", n_bars=5000)
            if h is not None and len(h) >= 300:
                h.index = h.index.normalize()
                h.to_csv(os.path.join(CACHE, f"{tk}.csv"))
        except Exception as e:
            log(f"{tk}: {type(e).__name__}: {e}")
        time.sleep(0.3)
    log("data refresh done")


def data_is_stale():
    today = pd.Timestamp.now().normalize()
    fp = os.path.join(CACHE, "NIFTY.csv")
    try:
        df = pd.read_csv(fp, usecols=["date"])
        return pd.to_datetime(df["date"]).max().normalize() < today
    except Exception:
        return True


def collect():
    ok, nifty_last = find_setups.regime_ok()
    ndf = pd.read_csv(os.path.join(CACHE, "NIFTY.csv"),
                      parse_dates=["date"], index_col="date")
    sma200 = float(ndf["Close"].rolling(200).mean().iloc[-1])
    dist = 100 * (float(ndf["Close"].iloc[-1]) / sma200 - 1)

    armed, supp = [], []
    fp_today = os.path.join(HERE, f"setups_{date.today()}.csv")
    fps = sorted(glob.glob(os.path.join(HERE, "setups_*.csv")))
    fp = fp_today if os.path.exists(fp_today) else (fps[-1] if fps else None)
    if fp:
        for attempt in range(2):
            try:
                df = pd.read_csv(fp)
                break
            except Exception:
                time.sleep(0.5)
                df = pd.DataFrame()
        if not df.empty and "action" in df.columns:
            armed = df[df["action"] != "SUPPRESSED_RS"].to_dict("records")
            supp = df[df["action"] == "SUPPRESSED_RS"].to_dict("records")
        elif not df.empty:
            armed = df.to_dict("records")

    log_rows = []
    log_fp = os.path.join(HERE, "signal_log.csv")
    if os.path.exists(log_fp):
        try:
            lg = pd.read_csv(log_fp, dtype=str)
            log_rows = lg.tail(25).iloc[::-1].to_dict("records")
        except Exception:
            pass

    return {
        "ok": ok, "nifty": nifty_last, "sma200": sma200, "dist": dist,
        "armed": armed, "supp": supp, "log": log_rows,
        "source": os.path.basename(fp) if fp else "-",
        "generated": pd.Timestamp.now().strftime("%d-%b-%Y %H:%M:%S"),
    }


def badge(kind):
    k = kind.split("(")[0]
    color = {"PULLBACK": "#00dbff", "BB_REV": "#ffb74d",
             "TIER2": "#ce93d8"}.get(k, "#eaeaea")
    return f'<span class="badge" style="background:{color}22;color:{color};border:1px solid {color}55">{html.escape(str(kind))}</span>'


LOGIC = """
<div class="lg">
<h3>1 · Universe &amp; data</h3>
<p>Top-150 NSE stocks by market cap (139 pass the minimum-history bar),
daily OHLCV from TradingView. Backtests run 2006→today on the same cached
files the scanner reads. Signals are computed on END-OF-DAY data after
market close — entries happen NEXT session at open, never intraday.</p>

<h3>2 · Regime gate (always applied)</h3>
<p>No NEW long positions unless Nifty &gt; its own 200-day moving average.
Existing positions are always managed by their stops regardless of the gate.
This single index-level filter flips the book off in bear phases.</p>

<h3>3 · RS≥90 quality gate (PULLBACK only)</h3>
<p>O'Neil-style relative strength: each stock's trailing 252-session return
is cross-sectionally ranked 1–99 against this universe on the signal date.
PULLBACK entries require RS ≥ 90. Evidence: uptrend-regime profit factor
1.38 → 1.72, gated portfolio CAGR 13.7% → ~27.6%, stable across 2010-17 and
2018-26 eras. BB_REV / TIER2 rows carry RS as info only.</p>

<h3>4 · Strategy A — TREND PULLBACK (core engine)</h3>
<table>
<tr><th>Element</th><th>Rule</th></tr>
<tr><td>Trend</td><td>Close &gt; SMA200 AND SMA200 higher than 20 sessions ago AND Close &gt; SMA50</td></tr>
<tr><td>Dip</td><td>Low touched SMA20 within the last 5 sessions</td></tr>
<tr><td>Trigger</td><td>Close &gt; previous session's high AND Close &gt; SMA20 (reclaim day)</td></tr>
<tr><td>Entry</td><td>Next session's open</td></tr>
<tr><td>Stop</td><td>min(lowest low of last 5 bars, entry − 2×ATR14) − 0.25×ATR buffer</td></tr>
<tr><td>Target</td><td>2 × risk (2R)</td></tr>
<tr><td>Time stop</td><td>Exit after 20 sessions if neither hit</td></tr>
</table>
<p><b>Evidence:</b> n=28,630 trades since 2006 · win 50.1% · avg +1.02%
net/trade · profit factor 1.34.</p>

<h3>5 · Strategy B — BB REVERSION (filler only)</h3>
<p>RSI14 &lt; 35 · Close &gt; SMA200 · Close ≤ lower Bollinger(20,2) × 1.02 ·
volume &lt; SMA10(volume). Entry next open; stop 1.5×ATR; exit at mid-band
(SMA20) or 8 sessions. <b>Evidence:</b> n≈1,016 · PF 1.28 — small edge,
used to keep slots busy, never sized up.</p>

<h3>6 · Strategy C — TIER-II SYMPATHY</h3>
<p>When a sector LEADER (largest market-cap stock of its sector) pops
≥ +5% on ≥ 2× normal volume, buy the same-sector LAGGARD that: correlates
≥ 0.55 over 120 sessions, moved less than half the leader's gain, sits above
a rising SMA200, and clears the ₹5 Cr/day liquidity floor. Same stop
geometry as PULLBACK, 10-session time stop. <b>Evidence:</b> n=66 ·
PF 1.61 overall, 2.02 in Nifty uptrends. <b>Caveat:</b> currently running
on an interim Yahoo sector map (coarser) — treat TIER2 rows as
lower-confidence until the original map is restored.</p>

<h3>7 · Position sizing</h3>
<p>Capital ₹6,00,000 · risk 1.5% per trade = ₹9,000 ·
qty = ⌊9,000 ÷ (entry − stop)⌋ · hard notional cap ₹1,50,000 per position ·
maximum 6 concurrent slots. All backtest numbers already include 0.30%
round-trip costs.</p>

<h3>8 · Robustness evidence</h3>
<ul>
<li><b>Fragility sweep:</b> stop buffer 0→0.5×ATR and target 1.5R→3R sit on
smooth plateaus (PF 1.31–1.37). The 20-session time stop is the one
sensitive knob — shortening it collapses the edge. Never shorten it.</li>
<li><b>Monte Carlo</b> (2,000 paths on the actual 1,294-trade taken
sequence): terminal equity 90% CI [31×, 284×]; forward-12-month projection
median +27%, probability of a negative year ≈ 5.5%. Realized tails were
worse than bootstrap bands — expect drawdowns beyond −30% and losing
streaks up to ~18 trades.</li>
</ul>

<h3>9 · Tested and REJECTED (kept out on purpose)</h3>
<p>52-week-high breakout (PF 0.94) · PEAD proxy · entire short side ·
metals/crypto regime timing · ADX strength filter · post-crash cooldown ·
fundamental PAT&lt;0 gate (unvalidatable data) · golden-pocket fib depth
(redundant after RS≥90) · SMC/FVG/order-block suite · PCR / Max Pain /
OI walls (intraday phenomena, no validatable history).</p>

<h3>10 · Known caveats</h3>
<p>Universe = today's large caps → survivorship bias makes backtest numbers
upper bounds. Sector map interim (see #6). Signals go stale — re-run the
scanner before acting on any levels shown here.</p>
</div>
"""


FAMILY_ALLOC = {
    "headline": [
        ("Nifty 50", 20), ("Nifty Next 50", 12), ("Mid Cap 150", 20),
        ("Small Cap 250", 5), ("US Equity", 15), ("Flexi Cap", 5),
        ("Gold", 10), ("Arbitrage", 8), ("Liquid/Cash", 5),
    ],
    "books": [
        ("Personal — Monthly SIP ₹2,00,000/mo", [
            ("Navi Nifty 50 Index", "₹40,000", "20%"),
            ("Kotak Nifty Next 50", "₹24,000", "12%"),
            ("Invesco India Mid Cap", "₹40,000", "20%"),
            ("Bandhan Small Cap", "₹10,000", "5%"),
            ("US: VOO ₹15K + QQQM ₹10K + SOXQ ₹5K", "₹30,000", "15%"),
            ("PPFAS Flexi Cap", "₹10,000", "5%"),
            ("GoldBees ETF", "₹20,000", "10%"),
            ("Arbitrage Fund (direct-growth)", "₹16,000", "8%"),
            ("Liquid Fund", "₹10,000", "5%"),
        ]),
        ("Wife — Weekly STP ₹30,000/wk (₹1,20,000/mo)", [
            ("Navi Nifty 50 Index", "₹6,000", "20%"),
            ("Kotak Nifty Next 50", "₹3,500", "11.7%"),
            ("Invesco India Mid Cap", "₹6,000", "20%"),
            ("Bandhan Small Cap", "₹1,500", "5%"),
            ("US feeder FoF", "₹4,500", "15%"),
            ("PPFAS Flexi Cap", "₹1,500", "5%"),
            ("GoldBees ETF", "₹3,000", "10%"),
            ("Arbitrage Fund", "₹2,500", "8.3%"),
            ("Liquid Fund", "₹1,500", "5%"),
        ]),
        ("Mother — Weekly STP ₹35,000/wk (₹1,40,000/mo)", [
            ("Navi Nifty 50 Index", "₹7,000", "20%"),
            ("Kotak Nifty Next 50", "₹4,250", "12.1%"),
            ("Invesco India Mid Cap", "₹7,000", "20%"),
            ("Bandhan Small Cap", "₹1,750", "5%"),
            ("US feeder FoF", "₹5,250", "15%"),
            ("PPFAS Flexi Cap", "₹1,750", "5%"),
            ("GoldBees ETF", "₹3,500", "10%"),
            ("Arbitrage Fund", "₹2,750", "7.9%"),
            ("Liquid Fund", "₹1,750", "5%"),
        ]),
        ("HUF — Weekly STP ₹75,000/wk (₹3,00,000/mo)", [
            ("Navi Nifty 50 Index", "₹15,000", "20%"),
            ("Kotak Nifty Next 50", "₹9,000", "12%"),
            ("Invesco India Mid Cap", "₹15,000", "20%"),
            ("Bandhan Small Cap", "₹3,750", "5%"),
            ("US feeder FoF", "₹11,250", "15%"),
            ("PPFAS Flexi Cap", "₹3,750", "5%"),
            ("GoldBees ETF", "₹7,500", "10%"),
            ("Arbitrage Fund", "₹6,000", "8%"),
            ("Liquid Fund", "₹3,750", "5%"),
        ]),
    ],
    "blended": [
        ("Nifty 50", "₹1,52,000", "20.0%"), ("Nifty Next 50", "₹91,000", "12.0%"),
        ("Mid Cap", "₹1,52,000", "20.0%"), ("Small Cap", "₹38,000", "5.0%"),
        ("US Equity", "₹1,14,000", "15.0%"), ("Flexi Cap", "₹38,000", "5.0%"),
        ("Gold", "₹76,000", "10.0%"), ("Arbitrage", "₹61,000", "8.0%"),
        ("Liquid/Cash", "₹38,000", "5.0%"),
    ],
}


def alloc_tab():
    head = "".join(f"<tr><td>{n}</td><td>{p}%</td></tr>" for n, p in FAMILY_ALLOC["headline"])
    books = ""
    for title, items in FAMILY_ALLOC["books"]:
        rows = "".join(f"<tr><td>{html.escape(n)}</td><td>{a}</td><td>{p}</td></tr>"
                       for n, a, p in items)
        books += f"<h2>{html.escape(title)}</h2><table><tr><th>Fund</th><th>Amount</th><th>%</th></tr>{rows}</table>"
    blend = "".join(f"<tr><td>{n}</td><td>{a}</td><td>{p}</td></tr>" for n, a, p in FAMILY_ALLOC["blended"])
    return f"""
<div class="lg">
<p style="margin-top:0">Long-term family plan (separate from the ₹6L swing satellite).
Source of truth: <span class="mono">CORRECTED_ALLOCATION_V4.md</span>; dashboard generator
<span class="mono">src/dashboard_gen.py</span>. Total deployment ₹7,60,000/mo across four books.</p>

<h2>Headline target blend</h2>
<table><tr><th>Category</th><th>Target %</th></tr>{head}</table>
{books}
<h2>Family blended verification — ₹7,60,000/mo</h2>
<table><tr><th>Category</th><th>₹/month</th><th>Blended %</th></tr>{blend}</table>
<div class="lg" style="font-size:13px;color:#8b949e">
Notes: US for Wife/Mother/HUF via Indian feeder FoFs (post-Apr-2023 feeders taxed at slab
rate — if that drag matters, concentrate US in the Personal book; family total stays 15%).
Arbitrage funds are equity-taxed and hold the correction-deployment reserve (deploy per
tier rules at Nifty −15/−20/−25/−30%). Goal math: ₹7.6L/mo × 19 yrs ≈ ₹39 Cr @8%,
₹49 Cr @10%, ₹61 Cr @12%.
</div>
</div>
"""


def render():
    s = STATE
    gate_cls = "open" if s["ok"] else "closed"
    gate_txt = ("REGIME GATE OPEN — longs allowed"
                if s["ok"] else "REGIME GATE CLOSED — watchlist only")
    rows_a = ""
    for r in s["armed"]:
        rows_a += (f"<tr><td>{badge(r.get('setup',''))}</td>"
                   f"<td><b>{html.escape(str(r.get('ticker','')))}</b></td>"
                   f"<td>{r.get('entry_zone','')}</td><td>{r.get('stop','')}</td>"
                   f"<td>{r.get('target_2R','')}{(' / ' + str(r['target_mid'])) if r.get('target_mid') else ''}</td>"
                   f"<td>{r.get('qty','')}</td><td>{r.get('notional','')}</td>"
                   f"<td>{r.get('rs','')}</td><td>{r.get('rsi','')}</td></tr>")
    rows_s = "".join(
        f"<tr><td>{badge(r.get('setup',''))}</td>"
        f"<td><b>{html.escape(str(r.get('ticker','')))}</b></td>"
        f"<td>{r.get('entry_zone','')}</td><td>{r.get('rs','')}</td>"
        f"<td>RS&lt;90</td></tr>" for r in s["supp"])
    rows_l = "".join(
        f"<tr><td>{r.get('signal_date','')}</td>"
        f"<td>{html.escape(str(r.get('ticker','')))}</td>"
        f"<td>{html.escape(str(r.get('setup','')))}</td>"
        f"<td>{r.get('action','')}</td><td>{r.get('entry_zone','')}</td>"
        f"<td>{r.get('gate','')}</td></tr>" for r in s["log"])
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Swing Scanner</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{background:#0d1117;color:#e6e6e6;font-family:Segoe UI,Arial,sans-serif;margin:24px}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#8b949e;font-size:13px;margin-bottom:14px}}
.nav{{display:flex;gap:8px;margin-bottom:18px}}
.nav button{{background:#161b22;color:#8b949e;border:1px solid #30363d;padding:8px 18px;border-radius:8px;font-size:14px;cursor:pointer}}
.nav button.on{{color:#e6e6e6;border-color:#58a6ff;background:#1c2a3a}}
.banner{{padding:14px 18px;border-radius:10px;font-weight:600;font-size:16px;margin-bottom:18px}}
.open{{background:#12351f;border:1px solid #2ea043;color:#3fb950}}
.closed{{background:#3b1620;border:1px solid #e5534b;color:#f85149}}
.dist{{font-weight:400;font-size:13px;opacity:.85;display:block;margin-top:4px}}
table{{border-collapse:collapse;width:100%;margin-bottom:8px;font-size:14px}}
th{{text-align:left;color:#8b949e;font-weight:600;padding:8px 10px;border-bottom:1px solid #30363d}}
td{{padding:8px 10px;border-bottom:1px solid #21262d;vertical-align:top}}
tr:hover td{{background:#161b22}}
.badge{{padding:2px 10px;border-radius:20px;font-size:12px}}
h2{{font-size:15px;text-transform:uppercase;letter-spacing:1px;color:#8b949e;margin:26px 0 8px}}
.none{{color:#8b949e;font-style:italic}}
.footer{{margin-top:28px;padding-top:12px;border-top:1px solid #30363d;color:#8b949e;font-size:12px;line-height:1.6}}
.mono{{font-family:Consolas,monospace}}
.lg h3{{font-size:15px;color:#58a6ff;margin:22px 0 6px}}
.lg p,.lg li{{font-size:14px;line-height:1.65;color:#c9d1d9;margin:6px 0}}
.lg ul{{margin:6px 0;padding-left:22px}}
.hidden{{display:none}}
</style></head><body>
<h1>Swing Scanner — validated setups</h1>
<div class="sub">source artifact: {html.escape(s['source'])} · generated {s['generated']} · page reloads every {PAGE_RELOAD_SECS}s · data rescan every {INTERVAL}s</div>
<div class="nav">
<button data-t="live" onclick="showTab('live')">Live Setups</button>
<button data-t="logic" onclick="showTab('logic')">Methodology</button>
<button data-t="alloc" onclick="showTab('alloc')">Family Plan</button>
</div>
<div id="tab-live">
<div class="banner {gate_cls}">{gate_txt}
<span class="dist">Nifty {s['nifty']:,} vs 200-DMA {s['sma200']:,.0f} ({s['dist']:+.2f}%)</span></div>
<h2>Armed setups ({len(s['armed'])})</h2>
{'<table><tr><th>Setup</th><th>Ticker</th><th>Entry zone</th><th>Stop</th><th>Target</th><th>Qty</th><th>Notional ₹</th><th>RS</th><th>RSI</th></tr>' + rows_a + '</table>' if rows_a else '<div class="none">No qualifying setups.</div>'}
{('<h2>RS-suppressed (' + str(len(s['supp'])) + ')</h2><table><tr><th>Setup</th><th>Ticker</th><th>Entry zone</th><th>RS</th><th>Reason</th></tr>' + rows_s + '</table>') if rows_s else ''}
<h2>Signal log (latest 25)</h2>
<table><tr><th>Date</th><th>Ticker</th><th>Setup</th><th>Action</th><th>Entry zone</th><th>Gate</th></tr>{rows_l}</table>
<div class="footer">Sizing: ₹6,00,000 satellite · risk 1.5%/trade (₹9,000) · max notional ₹1,50,000 · 6 slots.<br>
Execution: enter NEXT session near signal close (limit orders) · resting SL at broker on fill · exits per validated rules (pullback/tier2 2R + 20d/10d time stop · bb_rev SMA20 or 8d).<br>
Entries allowed ONLY while gate OPEN. Display mirrors CLI output — no trading logic here.</div>
</div>
<div id="tab-logic" class="hidden">{LOGIC}</div>
<div id="tab-alloc" class="hidden">{alloc_tab()}</div>
<script>
const TABS = ['live', 'logic', 'alloc'];
function showTab(id){{
  TABS.forEach(t => document.getElementById('tab-'+t).style.display = t===id ? 'block' : 'none');
  document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('on', b.dataset.t===id));
  if(location.hash !== '#'+id) history.replaceState(null,'','#'+id);
}}
window.addEventListener('load', ()=>showTab(TABS.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'live'));
setTimeout(()=>location.reload(), {PAGE_RELOAD_SECS * 1000});
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path.startswith("/healthz"):
                body = b"ok"
            else:
                FIRST.wait(timeout=180)
                body = (render().encode("utf-8") if STATE
                        else b"<h1>scanning... first pass in progress</h1>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            log("request error:\n" + traceback.format_exc())
            try:
                msg = ("<pre>" + html.escape(traceback.format_exc()[-1500:])
                       + "</pre>").encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def log_message(self, *a):
        pass


def worker():
    global STATE
    while True:
        t0 = time.time()
        try:
            if data_is_stale() and time.time() - _last_data_attempt > 3600:
                refresh_data()
            STATE = collect()
            FIRST.set()
            log(f"state updated ({len(STATE['armed'])} armed, gate "
                f"{'OPEN' if STATE['ok'] else 'CLOSED'})")
        except Exception:
            log("worker error:\n" + traceback.format_exc())
        time.sleep(max(30, INTERVAL - (time.time() - t0)))


class Server(ThreadingHTTPServer):
    allow_reuse_address = False


def main():
    port, srv = None, None
    for p in range(PORT_BASE, PORT_BASE + 10):
        try:
            srv = Server(("127.0.0.1", p), Handler)
            port = p
            break
        except OSError:
            log(f"port {p} in use, trying next")
    if srv is None:
        raise OSError(f"no free port in {PORT_BASE}-{PORT_BASE + 9}")
    threading.Thread(target=lambda: (time.sleep(1.5),
                                     _try_open(port)), daemon=True).start()
    threading.Thread(target=worker, daemon=True).start()
    log(f"serving http://localhost:{port}  PID={os.getpid()}  "
        f"(rescan every {INTERVAL}s, page reload {PAGE_RELOAD_SECS}s)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("stopped (Ctrl+C)")


def _try_open(port):
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception as e:
        log(f"could not auto-open browser: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        log("FATAL:\n" + traceback.format_exc())
        traceback.print_exc()
        try:
            input("\n[scan_web] crashed - press Enter to close ...")
        except EOFError:
            pass
