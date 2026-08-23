# VALIDATED SWING SYSTEM — Complete Documentation
## Evidence-based trading system for the satellite book
*Created: Aug 21, 2026 | Data through: Aug 21, 2026*

---

## 0. ONE-PAGE SUMMARY

| Component | Rule |
|---|---|
| Core engine | Trend Pullback (validated PF 1.34) + RS≥90 quality gate (§16) |
| Filler | Bollinger Band Reversion (PF 1.28, capacity-limited) |
| Supplementary | Tier-II Sympathy (Scan E, PF 1.61 overall / 2.02 gated, ~3-4/yr) |
| Market gate | No new longs unless Nifty > its 200-day SMA |
| Risk per trade | 1.5% of ₹6L satellite = ₹9,000 |
| Max positions | 6 concurrent, max ₹1.5L notional each |
| Exits | Fixed at entry: targets, ATR stops, time stops |
| Review | Monthly vs Nifty; kill switch on 6-month underperformance |
| Rejected | 52W-high breakouts, gap/news buying (negative edge after costs); ALL short-side mirrors (doc 14) |

**Current status (Aug 21, 2026, final close): GATE CLOSED** — Nifty 24,252
vs 200-DMA ~24,687 (−1.77%), below since Feb 26, 2026. Armed watchlist (12
setups, verified on closing prices) in `watchlist_new_2026-08-21.csv`; no
entries until gate reopens.

---

## 1. RESEARCH FOUNDATION — WHY THESE STRATEGIES

Four strategy families were backtested on real data before trusting any:

- **Data:** 139 large/mid-cap NSE stocks (top ~150 by market cap), daily bars
  from TradingView's feed back to **2006** (~20 years)
- **Realism:** entry at next day's open after signal; exits checked against
  intraday high/low; **0.30% round-trip costs** on every trade
- **Portfolio sim:** ₹12L capital, max 6 simultaneous equal-weight slots

### Results (20 years)

| Strategy | Trades | Win% | Avg/trade | PF | Ungated CAGR | Regime-gated CAGR |
|---|---|---|---|---|---|---|
| Trend Pullback | 28,630 | 50.1% | +1.02% | 1.34 | 9.2% | **13.7%** ✅ |
| BB Reversion | 1,016 | 53.2% | +0.55% | 1.28 | 2.6% | 4.1% |
| 52W-High Breakout | 10,862 | 35.7% | −0.19% | 0.94 ❌ | −7.3% | −1.2% |
| Gap-buy (PEAD proxy) | 835 | 32.0% | +0.03% | 1.01 ❌ | −0.8% | −1.7% |

Benchmark: **Nifty buy-and-hold = 11.0% CAGR** over the same period.
Only Trend Pullback + regime gate beat it (13.7%).

### Key lessons from the research
1. Claimed win rates do not survive mechanical testing (docs claimed 85% for
   BB reversion; measured: 53%). The missing edge lives in discretionary
   checklist items — which is why BB reversion here requires manual
   confirmation of reversal candle + no events.
2. Every strategy earns in uptrend regimes and dies in downtrends → the gate
   is worth more than any entry signal.
3. Breakouts fail after costs at daily granularity across midcaps. This
   includes tip-style calls (e.g., "Genus Power to ₹500").
4. Survivorship bias means these numbers are *upper bounds* — real results
   would be somewhat worse. Trade smaller than feels necessary.

---

## 2. CORE ENGINE — TREND PULLBACK

### Logic
In an established uptrend, quality stocks get briefly sold down
(profit-booking, one bad headline). Institutions buy those dips because the
trend hasn't changed. You join an existing uptrend at a temporary discount,
with a stop just below the dip. No prediction involved.

### Entry conditions — ALL 5 must be true on the signal day

| # | Condition | Code | Purpose |
|---|---|---|---|
| 1 | Close > SMA200 | `Close > SMA200` | Long-term uptrend only |
| 2 | 200-DMA rising | `SMA200 > SMA200[20 bars ago]` | Fake uptrends filtered out |
| 3 | Medium trend up | `Close > SMA50` | Intermediate confirmation |
| 4 | Dipped to SMA20 in last 5 days | `Low ≤ SMA20` within 5 bars | The pullback actually happened |
| 5 | Strength reclaimed today | `Close > Prev High AND Close > SMA20` | Buyers stepped back in |
| 6 | RS rating ≥ 90 (adopted Aug 2026, §16) | trailing 12-mo return ranked vs cached universe | Trade only market LEADERS |

**Entry:** next session, near signal close (limit order).

### Exits (fixed before entry)
- **Stop:** `min(5-day low, entry − 2×ATR) − 0.25×ATR`
- **Target:** entry + 2R (twice the per-share risk)
- **Time stop:** exit after 20 days if neither hits

### Evidence
28,630 trades / 20y: 50.1% win, +1.02%/trade net, PF 1.34 overall;
PF 1.38 in up-regimes. In down-regimes expectancy drops to +0.27%/trade —
hence the gate. With the RS≥90 filter (§16): +2.06%/trade in up-regimes,
PF 1.62; gated portfolio CAGR 13.7% → 30.6% (see caveats there).

### Worked example — Hindustan Zinc (signal Aug 21, 2026)
```
Close 596 > SMA200 ✓   200-DMA rising ✓   > SMA50 ✓
Dipped to SMA20 this week ✓   Closed above yesterday's high ✓
Stop  = 544.70        risk/share = 51.20
Target = 596 + 2×51.20 = 698
Qty = 175 (see sizing math, §5)
```

---

## 3. FILLER — BOLLINGER BAND REVERSION

### Logic
A stock in a long-term uptrend that falls 2 standard deviations below its
20-day mean is statistically stretched and usually snaps back to the mean.
You are selling fear, not catching knives — the SMA200 filter is what makes
it safe.

### Entry conditions — ALL must be true
1. RSI(14) < 35
2. Close > SMA200 (took win rate ~45% → ~56% in backtest)
3. Close ≤ Lower Bollinger Band (20, 2) × 1.02

### Manual confirmation required (from STRATEGY_1 doc checklist)
- Reversal candle formed (hammer / bullish engulfing)
- No major event/earnings within 3 days
- Volume declining at the band touch

### Exits
- Stop: entry − 1.5×ATR
- Target: middle band (SMA20)
- Time stop: 8 days

### Evidence
1,016 trades / 20y: 53.2% win, PF 1.28 overall; **PF 1.49, 56% win in
up-regimes**; PF 0.82 (losing) in down-regimes. Capacity-limited: few
signals, capital often idle → treat as filler when signals appear.

### Current candidates (Aug 21, 2026)
BSE Ltd (RSI 31.7) and Cummins India (RSI 32.2) — both parked until gate
reopens + reversal candle confirms.

---

## 4. THE REGIME GATE — THE MOST VALUABLE RULE

**Rule: no new long positions unless Nifty 50 closes above its own 200-day SMA.**

Per-trade returns by regime (from validation):

| Strategy | Up-regime | Down-regime |
|---|---|---|
| Trend Pullback | +1.14%/trade | +0.27%/trade |
| BB Reversion | PF 1.49 | PF 0.82 (loses) |

Gating improved pullback portfolio CAGR 9.2% → **13.7%** purely by skipping
bad periods. One rule, ~4.5%/yr of value.

**Status history:** Nifty closed below its 200-DMA on Feb 26, 2026 and has
remained below through Aug 21, 2026 (24,230 vs 24,687, −1.85%). All setups
found during this period are armed watchlist entries only.

---

## 5. POSITION SIZING — CONSTANT RISK MATH

```
Capital            = ₹6,00,000 (satellite allocation)
Risk per trade     = 1.5% × 6,00,000 = ₹9,000
Risk per share     = entry − stop
Qty                = min( 9,000 ÷ risk_per_share , 150,000 ÷ entry )
Notional cap       = ₹1,50,000 per position (25% of satellite)
Max open           = 6 positions
```

Example (Hindustan Zinc):
```
Risk/share = 596 − 544.70 = 51.20
Qty by risk    = 9,000 ÷ 51.20  = 175
Qty by notional= 150,000 ÷ 596  = 251  → take min = 175 shares
Actual risk if stopped = 175 × 51.20 = ₹8,960 ≈ 1.5% ✓
```
This is why qty varies (3 shares of ABB Power vs 494 Vedanta): risk is
constant, price is not. A stop-out should never cost more than a planned
1.5%.

---

## 6. TECHNICAL IMPLEMENTATION — HOW STOCKS ARE FOUND

```
tv_history.py
  Connects anonymously to TradingView's websocket data feed.
  Downloads 5,000 daily OHLCV bars per symbol (back to ~2006).
  Saves to _price_cache/<SYMBOL>.csv; refreshes if older than 5 days.

strategy_validation.py          (research tool — rerun quarterly)
  get_universe()      top-150 NSE stocks by market cap via TV screener
  add_indicators()    SMA20/50/200, RSI14 (Wilder), BB(20,2), ATR14 (Wilder),
                      volume averages, 252-day highs
  signals()/simulate() generates signals per strategy, walks forward bar by
                      bar applying stop/target/time exits with intraday checks
  portfolio_cagr()    6-slot overlay, optional regime gating
  Output: console report + strategy_validation.json

find_setups.py                  (daily scanner — run after 3:45 PM)
  1. Loads cached price files, computes indicators
  2. Checks Part-2 conditions -> PULLBACK signal
  3. Checks Part-3 conditions -> BB_REV signal
  4. Checks Scan E leader/laggard logic (doc 13b) -> TIER2 signal
  5. Reads _price_cache/NIFTY.csv -> regime gate check
  6. Sizes every signal with the §5 formula
  Output: console table + setups_<date>.csv

test_tier2_sympathy.py          (Scan E validator — rerun with quarterly check)
  Codifies + simulates the sympathy rule; sensitivity matrix in
  test_tier2_sensitivity.py. Sector map cached in _price_cache/sectors.csv.

satellite_tracker.py            (monthly review)
  Reads trade_journal.csv -> realized P&L, win rate, avg R
  Compares rolling 6M performance vs Nifty -> OK / WARN / STOP verdict
```

---

## 7. RISK FRAMEWORK — LAYERED DEFENSE

| Layer | Rule | Enforced by |
|---|---|---|
| Trade | Max 1.5% capital risk | Sizing formula |
| Position | Max ₹1.5L notional | Sizing formula |
| Portfolio | Max 6 concurrent positions | Discipline / tracker |
| Market | Regime gate | find_setups.py |
| Strategy | Fixed stops/targets/time stops — never widened | Journal review |
| Meta | Kill switch: <Nifty over rolling 6M → halve size; again → stop for quarter | satellite_tracker.py |

---

## 8. OPERATING ROUTINE

| When | Action | Command |
|---|---|---|
| Daily 3:45 PM | Scan for setups | `py find_setups.py` |
| Daily | Gate green? Enter top-ranked next morning with limit orders + mandatory stops. Gate red? Do nothing. | — |
| On fill | Log entry to journal | trade_journal.csv |
| Weekly | Update journal exits; move stops per rules only | — |
| Monthly | Performance review + kill-switch check | `py satellite_tracker.py` |
| Quarterly | Re-validate edges haven't decayed | `py strategy_validation.py` |

---

## 9. FILE INVENTORY

| File | Role |
|---|---|
| `tv_history.py` | TradingView daily-data fetcher (websocket, cached) |
| `strategy_validation.py` | 20-year strategy validator (research) |
| `strategy_validation.json` | Latest validation numbers |
| `find_setups.py` | Daily live setup scanner with sizing (PULLBACK / BB_REV / TIER2) |
| `setups_<date>.csv` | Each day's detected setups |
| `trade_journal.csv` | Every trade logged (open + closed) |
| `satellite_tracker.py` | Monthly benchmark review + kill switch |
| `watchlist_new_2026-08-21.csv` | Armed watchlist (GATED-WAIT entries) |
| `test_tier2_sympathy.py` + `test_tier2_sensitivity.py` | Scan E validator + robustness matrix |
| `test_short_side.py` | Short-mirror rejection evidence (doc 14) |
| `test_momentum_filters.py` | O'Neil RS / Minervini template filter research (doc 16) |
| `book/` | Extracted text of reviewed external books (evidence trail) |
| `_price_cache/` | Cached daily OHLCV for universe + NIFTY (+ sectors.csv map) |

---

## 10. PHILOSOPHY — WHAT THIS SYSTEM IS AND ISN'T

**Is:** two simple, validated edges (pullback + mean reversion), executed
mechanically inside a strict risk container, benchmarked monthly against
passive indexing.

**Isn't:** prediction, tips, high-win-rate marketing, or a path to ₹1L/month
on ₹15L. Realistic expectation: beat Nifty by 3–5%/yr with lower drawdowns.
If it can't do that over rolling 12-month windows, the kill switch folds it
back into the core index portfolio — which is exactly how professionals
treat satellite books.

---

## 11. HOW TO USE — PRACTICAL OPERATING GUIDE

### Step 0 — While the gate is CLOSED (current state)
1. Set price alerts on the armed setups in
   `watchlist_new_2026-08-21.csv` (entry zones listed there)
2. Manage open positions only: trail stop to entry at +1.5x risk; take half
   off if stalling
3. Cash is a position. The system's first job is keeping you out of bad
   markets.

### Daily routine (10 minutes, after 3:45 PM)

```
Step 1   Terminal in E:\PortfolioTracker\SwingTrading
Step 2   py find_setups.py
Step 3   Read the FIRST output line:
```

| Gate says | You do |
|---|---|
| `OPEN` | Pick max 1-2 best signals -> limit orders for next morning near entry zone |
| `CLOSED` | Nothing. Log interesting signals as GATED-WAIT. Close terminal. |

Every order carries its stop-loss entered at the same time. No stop = no
trade. Qty comes from the output - never resize by feel.

### When the gate reopens (Nifty daily close above ~24,700)
1. Confirm it is a DAILY CLOSE, not an intraday poke
2. Pick top 2-3 from armed watchlist
3. BB Reversion names additionally need: reversal candle + no earnings
   within 3 days
4. Enter with pre-computed qty + stop
5. Log to trade_journal.csv within 5 minutes of fill
6. Max 1 new position per day

### Managing open trades (daily, 2 minutes)
- Stop hit -> exit. No exceptions.
- Target hit -> exit per rule (pullback: full at 2R; BB rev: at SMA20)
- Time stop reached (20d / 8d) with nothing happening -> exit flat
- Never widen a stop. Ever.

### Weekly / monthly tasks

| When | Command | Shows |
|---|---|---|
| Every Friday | `py satellite_tracker.py` | Open risk, closed-trade stats |
| Month-end | same | Rolling 6M vs Nifty -> OK / WARN / STOP |
| Quarterly | `py strategy_validation.py` | Edge decay check (~seconds, cached) |

Kill switch discipline: WARN -> halve all sizes. STOP -> no new trades for
the rest of the quarter. Follow it even when a "perfect" setup appears.

### The seven rules that make this work
1. The gate does the heavy lifting; most months the answer is "no trades"
2. Judge monthly against Nifty, never daily P&L
3. Boring consistency > excitement; 2-4 trades/month and zero-trade weeks
   are normal
4. Never act on tips/Telegram - outside ideas go through this pipeline or
   they don't exist
5. Journal every trade within 5 minutes of filling
6. Expectation: beat Nifty by 3-5%/yr with smaller drawdowns; if a trade
   "needs" to work, sizing is too big
7. When in doubt, do nothing - the edge comes from skipping bad trades more
   than picking good ones

### Quick reference card (print)

```
GATE:      Nifty > 200-DMA?  NO  -> hands off
RISK:      Rs.9,000/trade max, 6 slots, Rs.1.5L/position
ENTRY:     next-session limit near signal close, stop entered together
PULLBACK:  exit 2R / 20 days / stop below dip
BB REV:    exit at SMA20 / 8 days / stop 1.5xATR
REVIEW:    monthly vs Nifty . quarterly revalidation
KILL:      6M underperformance x2 -> stop for quarter
```

---

## 12. WORKED EXAMPLES — Aug 21, 2026 scan (real data)

### Example 1: HINDZINC — clean Trend Pullback pass

Last 6 sessions: dip to 548.8 (Aug 19) then reclaim to 594.9 (Aug 21 final).

```
1. Close > SMA200          594.9 > 572.1            PASS
2. SMA200 rising           572.1 > 564.6 (20d ago)  PASS
3. Close > SMA50           594.9 > 550.0            PASS
4. Dipped to SMA20 <=5d    lows 558/548.8 < SMA20 566.4   PASS
5. Reclaim                 594.9 > prev high 575.0 AND > SMA20  PASS
-> SIGNAL: PULLBACK
```

Sizing:
```
ATR ~ 16.3
Stop       = min(5d low 548.8, 594.9 - 2xATR) - 0.25xATR = 544.70
Risk/share = 50.20   Qty = 9000/50.20 = 179
Notional   = 179 x 594.9 = Rs.1,06,500 (< cap OK)
Target 2R  = 695.30
```

Outcomes: target +Rs.17,970 (2R) | stop -Rs.8,990 (1R) | day-20 time exit ~flat.
Win rate needed for profit at this asymmetry: just 34%.
NOT taken today: gate CLOSED outranks a perfect setup.

### Example 2: BSE Ltd — BB Reversion pass WITH warnings

```
1. RSI < 35                 RSI = 31.9                    PASS
2. Close > SMA200           3241.0 > 3231.1               PASS (by only 0.3%!)
3. Close <= Lower BB x1.02  3241.0 <= 3311.6 (BB_LO 3246.7)   PASS (below band)
-> SIGNAL: BB_REVERSION
```

Sizing — notional cap binds, not risk:
```
ATR ~ 105; Stop = 3241.0 - 1.5xATR = 3083.20
Risk/share = 157.80
Qty by cap = 150000/3241 = 46   <- smaller wins (cap binds)
Actual risk = 46 x 157.8 = Rs.7,260 (< 1.5%, safe side)
Target = SMA20 = 3476.70 -> R:R ~ 1:1.49
```

Human red flags (why manual confirmation exists):
- close barely above its own 200-DMA - one bad day kills condition #2
- no reversal candle yet (closed near session low)
- gate closed anyway

### The pattern every finding follows

conditions checked mechanically -> stop from structure+volatility ->
qty from fixed risk -> exits written BEFORE entry -> gate has veto over all.

---

## 13. EXTERNAL BOOK EVALUATION — "The Swing Trader's Bible"
*(McCall & Whistler, Wiley 2008; text extracted to `book/`, reviewed Aug 2026)*

17 strategies, anecdote-driven, no backtests in the book. Assessment vs our
validated engine (`test_rsix_variant.py` holds the reproducible test):

| Book strategy | Our verdict |
|---|---|
| Ch5 Envelopes/pitchforks | Subjective channel drawing; skip. Exuberance idea noted below |
| Ch6 RSI crossover (9-period, wait for cross back above 30) | **TESTED - FAILS** (see below) |
| Ch7 MACD/Stochastic | Uncoded oscillator variants; low prior after ch6 result |
| Ch8 Tier II sympathy plays | **TESTED - ADOPTED as Scan E** (see 13b below) |
| Ch9-10 Sector rotation / macro-to-micro | Index timing, out of satellite scope |
| Ch11 Exuberance premium fade | Shorting overbought = rejected direction for us |
| Ch12 Candlesticks | Anecdotal only; literature shows weak standalone edge |
| Ch13/19/20/21 Options (LEAPS, covered calls, straddles, spreads) | Out of cash-market scope |
| Ch14 Piggyback ETFs/MFs | Redundant with direct stock trading |
| Ch15 Scanning (breakout/oversold/volume/short-interest) | Breakout scan ≈ our hi52: we tested it, PF 0.94 REJECTED. Oversold scan ≈ our BB_REV: ours passed where theirs lacks trend filter |
| Ch16 Shorting sell-offs | Not practical in NSE cash market; our regime gate achieves the same protection by going to cash |
| Ch17 Megatrends | Vague thematic; not codifiable |
| Ch18 ROA/ROE filters | Swing horizon too short for fundamentals to matter |

### The RSIX test (their flagship idea)
Their claim: never buy oversold while falling - wait for RSI to cross back
above 30/35 as bottom confirmation. Tested three ways, same exits/costs:

```
BASELINE our BB_REV          n=1016  win=53.2%  avg=+0.55%  PF=1.28
A: book RSIX standalone      n= 619  win=51.2%  avg=-0.32%  PF=0.85   <- loses money
B: our setup + RSIX wait     n= 580  win=54.0%  avg=-0.01%  PF=1.00   <- edge destroyed
```

Why confirmation kills it: waiting for the turn means buying after the
bounce started - entry sits closer to the mid-band target, shrinking the
reversion profit while the ATR stop stays wide. The extreme-tap entry IS
the edge; the book's caution gives it away. Our guard against falling
knives is the trend context (close > rising SMA200), which survives testing.

**Lesson reinforced:** plausible trading wisdom must pay rent in backtest
results. Any future external idea gets the same treatment: codify -> run
through `strategy_validation.py` conventions -> adopt only if it beats the
incumbent.

### 13b. Scan E — TIER-II SYMPATHY (adopted from ch 8, validated Aug 2026)

Rule: when the largest stock in a sector (the "leader") pops >= +5% in a
day on >= 2x average volume, same-sector stocks that are highly correlated
to it (120d corr >= 0.55) but have NOT yet moved (< half the leader's
gain) tend to catch up within days. Buy the laggard next open.

Context filters (our discipline): laggard close > rising SMA200, 50d
turnover >= Rs.5 Cr. Exits: pullback-style - stop = min(5d low,
entry - 2xATR) - 0.25xATR, target 2R, time stop 10 days.

Results (139 symbols, 2006-2026, same costs):

```
overall            n= 66  win=57.6%  avg=+1.40%  PF=1.61
in NIFTY uptrend   n= 52  win=67.3%  avg=+2.07%  PF=2.02   <- trade it only here
in NIFTY downtrend n= 14  win=21.4%  avg=-1.10%  PF=0.66   <- regime gate handles this
```

Robustness (sensitivity matrix, all cells profitable -> not curve-fit):

```
corr>=0.45 lret>=5%   n=178  PF=1.19      corr>=0.55 lret>=4%  n=107  PF=1.19
corr>=0.55 lret>=5%   n= 66  PF=1.61      corr>=0.55 lret>=6%  n= 38  PF=1.36
corr>=0.60 lret>=5%   n= 32  PF=2.35      corr>=0.65 lret>=6%  n=  8  PF=3.25
```

Caveats: ~3-4 signals/year (supplementary, never forced); small sample -
size stays at standard Rs.9,000 risk, no scaling up; sector map cached in
`_price_cache/sectors.csv` (delete to refresh).

Live integration: `find_setups.py` now emits `TIER2(LEADER +x%)` rows with
full sizing. First live hits (Aug 21, 2026, gate closed -> GATED-WAIT):
ICICIBANK behind HDFCBANK +5.7%; ASHOKLEY/BHARATFORG/BOSCHLTD behind
MOTHERSON +8.7%.

---

## 14. THE SHORT SIDE — TESTED AND REJECTED (Aug 2026)

Question: our validated setups work long - do their MIRRORS harvest
bear-market periods instead of sitting in cash? Tested all four
(`test_short_side.py`, same 20y data, next-open fills, 0.30% costs,
adverse-move-first intraday checks):

```
SHORT-PULLBACK    n=14725  win=43.3%  PF=0.82   (uptrend 0.97 / downtrend 0.72)
SHORT-BBREV       n= 1759  win=42.2%  PF=0.66   (uptrend 0.70 / downtrend 0.62)
SHORT-BREAKDOWN   n= 2575  win=42.8%  PF=0.78   (uptrend 1.09 / downtrend 0.67)
SHORT-TIER2       n=   36  win=36.1%  PF=0.49
```

Every configuration loses. Even regime-aligned shorts (Nifty < 200-DMA,
where the long gate sits closed) lose badly. The lone positive cell
(breakdown-shorts during bull markets, PF 1.09 / +0.24%) is below every
adoption bar and smells of momentum-crash risk.

Why the mirror fails here (and globally):
1. Equity anomalies live on the LONG side - short legs carry borrow cost,
   squeeze risk, and fast-covering rallies (academic consensus, confirmed
   on this dataset).
2. India-specific: no delivery shorting; futures add rollover friction
   (~1-2%/yr) that makes real results WORSE than these simulations; SLB
   too thin for retail swing horizons.
3. Bear-market rallies in India are violent - stops at 1.5-2xATR get run
   over precisely when signals look best.

**System verdict unchanged:** gate closed -> CASH is the position. A
disaster-hedge via index PUTS is optional insurance (defined premium),
not a strategy. Do not re-test shorts without new structural evidence.

---

## 15. GOLD / SILVER / BITCOIN — TESTED AS TREND PORTFOLIO (Aug 2026)

Question: does our 200-DMA regime logic transfer to metals & BTC?
(`test_metals_crypto.py`, spot data via TradingView, 19y gold/silver,
13.7y BTC):

```
                 Buy&Hold                  200DMA regime
GOLD    +10.5%CAGR  -44.7%DD Sh0.64   +6.7%CAGR -33.0%DD Sh0.53  WORSE
SILVER  +9.0%CAGR   -75.3%DD Sh0.42   +6.4%CAGR -58.1%DD Sh0.37  WORSE
BITCOIN +88.2%CAGR  -84.9%DD Sh1.01   +63.5%CAGR -69.6%DD Sh0.96  WORSE
```

Verdict: the simple regime filter does NOT add return in these assets -
its only benefit is drawdown reduction (-12pts gold, -17 silver, -15 BTC).
Consistent with literature: single-asset 200DMA timing is weak; published
trend-following results come from DIVERSIFIED multi-market books and
short-side capture we deliberately don't run.

Portfolio guidance adopted:
- Gold/Silver = CORE diversification via ETFs (GOLDBEES/SILVERBEES),
  different return driver vs equities; hold through cycles, ignore our
  equity signals there. No tested swing edge -> never day/swing-trade them.
- BTC = optional speculative core, max ~5% of net worth, buy-and-hold
  mentality ONLY (India: 30% flat tax + 1% TDS kills active trading math).
- None of these belong in the Rs.6L satellite book.

---

## 16. MOMENTUM FILTER RESEARCH — O'NEIL RS & MINERVINI TREND TEMPLATE (Aug 2026)

The Aug-21 book deep-dive surfaced two classic stock-level quality filters for
pullback entries: O'Neil's RS Rating (trailing 12-month return ranked 1–99
within our cached universe) and Minervini's 8-point Trend Template (Stage-2
checklist incl. its own RS≥70). `test_momentum_filters.py` applied them as
ENTRY FILTERS on validated PULLBACK — filters only remove signals, exits and
slot logic unchanged. Decision metric = regime-gated portfolio CAGR:

| Variant | Trades | Up-regime avg/trade | Up-regime PF | GATED CAGR | GATED maxDD |
|---|---|---|---|---|---|
| Baseline PULLBACK | 28,630 | +1.14% | 1.38 | 13.7% | −40.7% |
| RS ≥ 70 | 14,399 | +1.49% | 1.49 | 18.0% | −36.7% |
| RS ≥ 80 | 10,066 | +1.64% | 1.52 | 19.7% | −36.6% |
| **RS ≥ 90** | 5,089 | **+2.06%** | **1.62** | **30.6%** | −36.7% |
| Trend Template | 12,000 | +1.49% | 1.48 | 24.8% | −35.3% |
| Template + RS≥85 | 6,779 | +1.75% | 1.54 | 19.0% | −36.9% |

Robustness checks on the RS≥90 result:
- Monotonic improvement across thresholds 70→80→90 (not a lucky single point).
- Era stability: PF 1.40 in 2010–17 AND 1.50 in 2018–26, while the unfiltered
  baseline DECAYS (1.38 → 1.30). The edge is strengthening, not fading.
- Large samples: 3,914 in-regime trades; portfolio overlay took 1,294 over
  ~17y (~76/yr ≈ 6–7 signals/month at 6 slots — capacity unaffected).
- Consistent with momentum-factor literature (Jegadeesh-Titman; NSE factor
  studies: Momentum ~14% CAGR, Sharpe 0.63).

Caveats: survivorship-biased top-150 universe inflates ALL variants equally
(relative comparison stands); RS is ranked within this universe only; the
30.6% portfolio CAGR carries compounding-path luck — the robust part is the
trade-level improvement (+2.06% vs +1.14%, R 0.17 vs 0.12).

ADOPTED: PULLBACK entries now require RS ≥ 90. `find_setups.py` computes it
from cached closes and prints how many setups were suppressed. First gated
scan (Aug 21): 4 of 6 PULLBACK setups suppressed; survivors POWERINDIA (91),
VEDL (92). BB_REV / TIER2 rows show RS info-only.

REJECTED as standalone additions:
- Trend Template by itself — downtrend-regime PF 0.97 means it adds nothing
  beyond our index gate, and its edge is dominated by the RS criterion.
- Template+RS≥85 stacking — non-monotonic vs simpler RS≥90 → overfit risk.
  Prefer the simplest filter on the monotonic gradient.

---

*Sources: local backtests (`strategy_validation.json`, 139 symbols, 2006–2026);
academic literature (Jegadeesh-Titman 1993, George-Hwang 2004, Moskowitz-Ooi-
Pedersen 2012); StockBench 2025 & KDD'26 LLM-trading studies; SEBI algo
framework 2025-26.*

---

## 17. Earnings-shock filters (BHARATFORG case) - REJECTED; sector-map incident

**Trigger:** Aug 21 TIER2 setup BHARATFORG sat on a fresh Q1 net loss after a
-9% results-day gap-down. User asked: should the scanner skip "freshly broken"
names? Two candidate filters defined:

- **Filter A - fundamental loss gate** (skip if latest reported quarter PAT < 0).
  **UNVALIDATABLE, not adopted.** TradingView screener currently returns no
  fundamentals at all (probe Aug 21: market_cap_basic / net_income_fq / etc.
  all null for 600 NSE names); yfinance carries only ~5 quarters (Mar-2025+),
  so there is no point-in-time quarterly history to test against 20 years of
  price data. A hard gate built on it would be unvalidated discretion. At most
  a future *display column* (`pat_last_q`) if a data source recovers.
- **Filter B - post-crash cooldown** (no entry within W sessions of an
  overnight gap <= THR on >= Vx VOL20). Fully backtested
  (`test_earnings_filter.py`, all three adopted strategies, 4 configs:
  -5%/1.5x/5d, -5%/1.5x/10d, -4%/1.2x/5d, -7%/2.0x/5d). **REJECTED:**
  - PULLBACK: flag fires on only 23-258 of 28,630 signals; per-trade stats
    identical with/without (avg +1.02%, PF 1.34); gated-CAGR swings
    (9.3%-16.8%) are path noise, non-monotone in threshold strength.
  - RS>=90 subset: flagged n=23 -> too few to even bootstrap; PF delta +0.01.
  - BB_REV: only positive per-trade blip (C3: PF 1.28->1.31 on n=46 removed)
    but DD worsens and other configs degrade. Noise.
  - TIER2: ZERO flagged trades in 58 signals - the sympathy gates already
    de-facto exclude freshly-crashed mates.
  - Why BHARATFORG slipped through is therefore NOT a missing cooldown rule:
    our setups' geometry (RSI 60-75, > SMA200, green trigger) almost never
    coexists with a fresh -5% gap. The correct response is process, not code:
    **manual checklist item** - before taking any setup, check whether results
    released within the last ~5 sessions and read the reaction. Judgment,
    documented as such, journal the decision.

**Sector-map incident (found during this test):** `_price_cache/sectors.csv`
was silently rewritten 18:53 Aug-21 with all-null sector/mcap values - a
cache-miss refetch hit a TradingView screener outage. Effects + fixes:
- `get_sector_map()` hardened (`test_tier2_sympathy.py`): cache accepted at
  >=90% symbol coverage with no null sectors; degenerate screener responses
  raise instead of overwriting the cache.
- Map rebuilt from yfinance (`rebuild_sectors.py`, 148/150 symbols, 11 Yahoo
  sectors; BAJAJ_AUTO/NAM_INDIA 404). Live scanner works again.
- **Caveat:** under the coarse Yahoo map the full-history TIER2 baseline is
  n=58 PF 1.19 (e17 PF 0.53) vs published n=66 PF 1.61 on the finer TV map -
  i.e. TIER2's edge is **sensitive to sector-map granularity**. Until the TV
  map is restored (rerun `rebuild_sectors.py` after the screener recovers)
  treat live TIER2 rows as lower-confidence; re-validate once canonical map
  returns.

*Sources: `test_earnings_filter.py` run output Aug-21; `_price_cache/sectors_yf.csv`;
yfinance quarterly_income_stmt probe.*

---

## 18. Fragility sweep + Monte Carlo (Aug 21) - system PASSES

**Part 1 fragility** (`test_fragility_mc.py`; numpy port of pullback exits,
anchor reproduced exactly: n=28630 PF=1.34 CAGR=13.7%):
- stop buffer 0 -> 0.5xATR: full-set PF 1.31-1.37, RS>=90 PF 1.52-1.59 -
  smooth PLATEAU, default sits mid-plateau. Wider buffer = fewer whipsaws,
  bigger per-loss; DD grows with width (-40.7% -> -48.6% full set).
- target 1.5R -> 3R: full PF 1.31-1.36 - plateau. Gated CAGR peaks at
  1.75-2R (14.1%/13.7%), decays to 10.1% at 3R as time-exits dominate.
- time stop: the one REAL gradient. 10d collapses the edge (PF 1.15 full /
  1.38 RS90), 15d weak (1.25/1.46), 20d and 30d healthy (1.34-1.38 /
  1.54-1.55). Rule: NEVER shorten the 20-day runway; it is a minimum viable
  hold, not a tuned magic number.
Verdict: no knife-edge parameters; edge is structural, not curve-fit.

**Part 2 Monte Carlo** (2000 paths on the ACTUAL taken sequence, n=1294;
realized: 94.1x terminal, CAGR 27.5%, maxDD -34.8%, longest losing
streak 18 trades):
- iid bootstrap: terminal 90% CI [31x, 284x] median 91x; CAGR [20.2%, 35.3%]
  median 27.3%; maxDD [-27.0%, -13.8%]; worst trailing-12m median -12%;
  losing streak median 9.
- block bootstrap (20-trade blocks): fatter tails - terminal [17x, 570x],
  CAGR 5th pct 16.3%.
- forward 12m projection (68-trade year from taken pool): median +27.3%,
  90% CI [-1.1%, +65.2%], **P(negative year) = 5.5%**.
- CAVEAT: realized maxDD (-34.8%) and streak (18) sit OUTSIDE the resampled
  90% bands - bootstrap dilutes adverse clustering. Size for realized-style
  tails (maxDD can exceed -30%, streaks ~18), not MC medians.

**Tooling:** `find_setups.py` now appends an idempotent `signal_log.csv`
(armed / SUPPRESSED_RS / GATE rows; dedup key date+ticker+setup-kind;
verified across reruns). Cache glob hardened to skip `sectors*` files after
`sectors_yf.csv` broke the loader. Note: under the interim Yahoo sector map
today's TIER2 rows are LT-led (BEL, HAL) vs MOTHERSON-led under the old TV
map - see section 17 granularity caveat.

*Sources: `test_fragility_mc.py` output Aug-21; `signal_log.csv`.*

---

## 19. "Indicator X" triage + H7 fib-depth test (Aug 21) - REJECTED

User submitted a multi-feature Pine indicator (WaveTrend reversals, RSI OB/OS,
trend ribbon, KC bands, MTF EMA/ADX dashboard, MTF S/R clusters, Gann swings,
auto golden-pocket fibs, volume profile POC, SMC suite). Triage against
existing evidence:

- Already covered or redundant: trend ribbon / EMA S/R / dashboard bias
  (regime gate + SMA200 structure), RSI OB/OS (display-only by its own docs),
  WaveTrend reversal triggers (counter-trend role = BB_REV filler; shorts
  rejected), KC bands (wide BB cousin).
- ALREADY TESTED AND REJECTED: ADX>21 strength column = H4 Gujral ADX test
  (section 15: CI touched zero, capacity starvation).
- Discretionary overlays, no codifiable rule: MTF S/R zones, Gann swing line,
  liquidity boxes, volume-profile POC.
- On the standing skip-list: SMC suite (FVG / order blocks / ChoCH / BOS).
- ONE testable hypothesis -> H7 below.

**H7 fib retracement depth** (`test_fib_depth.py`): SH = last confirmed
pivot high (k=3), SL_prev = 15-bar low before the rally, trough = low between
SH and signal day; depth = retrace fraction. Depth distribution of our
signals: median 0.73 (our SMA20-dip geometry already selects deep pullbacks).

Results (anchors reproduced exactly):
- FULL set: monotone with depth - PF 1.34 -> 1.35 -> 1.36 -> **1.42** at
  depth>=0.618 (avg +1.02 -> +1.24, era-stable e17 1.45 / e26 1.39).
  The GP BAND variant (0.50-0.786) is WORSE than baseline (PF 1.27): capping
  depth excludes the best trades; deeper-than-GP (>0.786) is fine.
- RS>=90 traded book: effect vanishes - PF 1.55 -> 1.57 at best; bootstrap
  mean-diff deep-vs-shallow within RS90: **[-0.43, +0.82] crosses zero**.
  Gated CAGR non-monotone (25.6-31.3% vs 27.6% baseline).

VERDICT: **REJECT both variants.** The RS>=90 gate already captures the
quality that deep retracements add; the specific golden-pocket band idea is
actively harmful. Secondary value: depth>=0.618 is a validated FALLBACK
quality proxy for stocks without a usable RS rank (e.g. fresh listings) if
ever needed - do not stack it on top of RS90 (no incremental edge, fewer
trades).

*Sources: `test_fib_depth.py` output Aug-21; bootstrap in-session.*

---

## 20. Option-chain coverage assessment (Aug 21) - one testable item queued

User asked whether anything important is missing from option-chain analysis.
Assessment for an overnight CASH-equity swing system (entries next open,
holds 2-20d):

- **India VIX regime overlay - IMPORTANT and testable -> QUEUED as H8.**
  Hypothesis: suppressing new longs when VIX is elevated/rising improves
  tail beyond the 200-DMA gate. Blocked: Yahoo rate-limited (^INDIAVIX
  probe failed Aug 21 evening); retry when cool, else assemble from NSE
  archives. Same adoption bar as every filter (monotone thresholds, era
  stability, no capacity starvation).
- **FII index-futures positioning** - moderate-prior macro context; daily
  participant-wise OI exists in NSE archives but assembly is heavy. PARKED;
  weekly FII flow notes already cover the macro read.
- **PCR / Max Pain / OI strike walls** - NOT important for this system.
  Intraday/expiry-day phenomena with thin evidence at swing horizons; no
  free point-in-time historical option-chain data exists, so per section 17
  logic these can never become validated rules here. Revisit only if/when
  trading expiries intraday (Gujral track).
- **IV crush / event vol** - relevant to option buyers, not cash equity. N/A.
- Operational note (process, not rule): expiry-day gamma can wick stops on
  cash positions; resting SL orders at broker (already mandated) is the
  mitigation.

VERDICT: nothing adoptable today; H8 is the only follow-up worth running.

*Sources: probe `_tmp_probe_vix.py` (rate-limited); NSE data availability review.*

---

## 21. Universe breadth test: Nifty 500 (Aug 21-22) - REJECTED as replacement

**Question:** the live system trades a top-150-by-mcap universe. Does widening to
Nifty 500 improve it? Sandbox `_price_cache_n500/` built (478/500 series; 22 recent
IPOs fail the 300-bar minimum by design). Same validated engine
(`test_fragility_mc.sim_pullback`, anchor reproduced), only the data dir differs.
Live top-150 pipeline untouched.

**Results (pullback, BASE buf.25 lb5 2R ts20, costs 0.30% RT):**

| Book | n | Win | Avg/trade | PF | Gated CAGR | MaxDD |
|---|---|---|---|---|---|---|
| N150 RS>=90 (LIVE) | 1,294 | 53% | +2.0% | **1.72** | **27.5%** | -34.8% |
| N500 RS>=90 | 13,628 | 50.4% | +1.86% | 1.46 | 25.3% | -38.6% |
| N500 RS>=95 | 6,234 | 49.8% | +1.85% | 1.42 | 18.8% | -48.2% |
| N500 RS>=97/98 | 3,356/1,877 | ~50% | +1.6-1.7% | 1.35 | 13-17% | -35/-48% |
| N500 full | 77,482 | 49.5% | +1.25% | 1.36 | 10.1% | -44.8% |

Era-stable on N500 RS90: PF 1.44 (2010-17) / 1.46 (2018-26).

**Cost stress (+20 bps small-cap slippage):** RS90 book PF 1.40, gated CAGR 22.8%
-> edge survives slippage assumptions.

**Why rejected despite PF 1.46 being respectable:**
1. **Threshold curve is monotone DOWN** (90->95->97->98 = 1.46->1.42->1.35->1.35):
   raising the bar does NOT recover the N150 quality. The 1.72 comes from mega-cap
   universe concentration, not from a transferable RS percentile cutoff.
2. **Breadth buys nothing:** candidate signals grew ~10x but slot-limited "taken"
   trades rose only ~12% (1,294 -> 1,449) - slots+gate bind first. Portfolio-level
   result is strictly worse (CAGR 25.3% vs 27.5%, DD -38.6% vs -34.8%).
3. **Bias grows:** today's N500 members backfilled to 2002 = stronger survivorship
   bias than the already-flattering N150 numbers.

VERDICT: stay on top-150 for live trading. Keep the sandbox for future uses that
genuinely need breadth (e.g., TIER-II sector maps across more sectors).

*Sources: `_fetch_n500.py`, `_n500_validate.py`, trades `_n500_pullback_trades.csv`,
fails list `_n500_fetch_fails.txt`.*

---

## 22. H9 - Entry gap/chase policy (Aug 23) - ADOPTED as execution safeguard

**Question (user Phase-1 item #1/#9):** engine enters unconditionally at next
open. Should we skip bad opens?

Variants tested on the anchor engine (baseline reproduced n=28630 PF=1.34
avg=+1.02 OK), RS>=90 book shown:

| Policy | n | PF | Avg | CAGR | DD |
|---|---|---|---|---|---|
| Baseline | 4,936 | 1.55 | +1.87% | 27.6% | -34.8% |
| chase <=0.25 ATR | 3,934 | 1.48 | +1.64% | 25.4% | -34.5% |
| **chase <=0.50 ATR** | 4,674 | **1.56** | **+1.89%** | **33.8%** | **-31.2%** |
| chase <=1.00 ATR | 4,886 | 1.57 | +1.92% | 31.0% | -32.1% |
| gap-through-stop skip | 4,933 | 1.55 | +1.87% | 27.8% | -34.8% |
| gap-dn + chase 0.5 | 4,671 | 1.56 | +1.89% | 30.6% | -32.5% |

Realism check (stop anchored to PLAN level = resting-SL behaviour):
baseline 28.9%/-35.3% vs combined 30.9%/-29.6%.

**HONEST READING:** per-trade edge is UNCHANGED by every filter (PF band
1.48-1.57 = noise; gap-skip fires 3x in 20y). The chase-0.5 CAGR jump is
compounding path noise, NOT alpha (same lesson as s18 fragility sweep).

**ADOPTED ANYWAY, framed correctly:**
- chase cap 0.5 ATR: costs nothing (PF identical), bounds real-world
  slippage beyond modelled 0.30% costs.
- gap-through-plan-stop skip: near-zero statistical footprint but removes
  the instant-stop-out fill scenario entirely.
- 0.25 cap REJECTED: too strict, measurably hurts (PF 1.48).

**Implemented in production:** `find_setups.chase_cap()` emits a
`max_chase` column on every row (PULLBACK/BB_REV/TIER2); execution footer
now reads "SKIP if next open < stop or > max_chase". Web page shows the
Max chase column; signal_log schema extended (`max_chase`). Also fixed
the "/nan" target display bug (pandas NaN truthiness) while touching the
renderer.

*Source: `test_gap_policy.py`.*
