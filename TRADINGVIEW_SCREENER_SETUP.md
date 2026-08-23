# TRADINGVIEW SCREENER SETUP — Bollinger Band Reversion
## Step-by-Step Guide to Find Stocks Meeting All Criteria

---

## METHOD 1: TradingView Stock Screener (No Code)

### Step 1: Open Screener
1. Go to TradingView.com
2. Click "Screener" in left menu
3. Select "Stock" → "India" → "NSE"

### Step 2: Add Filters (Tab: "Filters")

#### Filter 1: Price vs Bollinger Band
```
Indicator: Bollinger Bands
Condition: Price Cross Below Lower Band
Period: 20
StdDev: 2
```

#### Filter 2: RSI
```
Indicator: RSI
Condition: Less Than
Value: 35
Period: 14
```

#### Filter 3: Price vs SMA 200
```
Indicator: SMA
Condition: Price Greater Than
Period: 200
```

#### Filter 4: Volume
```
Indicator: Volume
Condition: Less Than
Value: Volume SMA 10
(Or: Volume < Average Volume 10)
```

#### Filter 5: Candlestick Pattern
```
Indicator: Candlestick Pattern
Condition: Is Hammer OR Is Bullish Engulfing
```

#### Filter 6: 20 SMA Slope
```
Indicator: SMA
Period: 20
Condition: Slope between -2% and +2%
(Use: SMA 20 change % between -2 and 2)
```

#### Filter 7: Market Cap
```
Market Cap: Greater Than ₹5,000 Cr
(Ensures liquidity)
```

#### Filter 8: Average Volume
```
Average Volume: Greater Than ₹10 Crore/day
(Ensures liquidity)
```

---

## METHOD 2: TradingView Pine Script Screener

### How to Use the Pine Script

1. Open TradingView → Pine Editor (bottom panel)
2. Copy the contents of `bb_reversion_screener.pine`
3. Paste into Pine Editor
4. Click "Add to Chart"
5. The script will:
   - Plot Bollinger Bands on your chart
   - Show green "BUY" triangles when ALL criteria met
   - Show yellow "Watch" circles when partial criteria met
   - Display an info table with all 6 coded conditions

### To Use as a Screener:
1. Add the indicator to any NSE stock chart
2. Check the info table in top-right corner
3. If all conditions show ✅ = VALID ENTRY
4. If any show ❌ = DO NOT TRADE

---

## METHOD 3: TradingView Alert-Based Scanner

### Set Up Alerts for All Nifty 50 Stocks:

1. Open TradingView → Alerts (clock icon on right)
2. Create Alert for each stock:
   - Condition: "BB Reversion Screener" → "BUY Signal"
   - Message: "BB Reversion: {{ticker}} at ₹{{close}}"
   - Webhook: (optional) Connect to Telegram/broker

### Nifty 50 Stocks to Monitor:

```
RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, HINDUNILVR, ITC,
SBIN, BHARTIARTL, KOTAKBANK, LT, AXISBANK, ASIANPAINT,
MARUTI, TITAN, SUNPHARMA, ULTRACEMCO, NESTLEIND, WIPRO,
TATAMOTORS, BAJFINANCE, ONGC, NTPC, TATASTEEL, POWERGRID,
M&M, TECHM, HCLTECH, ADANIENT, ADANIPORTS, TATACONSUM,
INDUSINDBK, BAJAJFINSV, COALINDIA, DRREDDY, BPCL, DIVISLAB,
GRASIM, CIPLA, APOLLOHOSP, EICHERMOT, BRITANNIA, HEROMOTOCO,
SBILIFE, HINDALCO, TRENT, ICICIPRULI, BAJAJ-AUTO, LTIM, SHRIRAMFIN
```

---

## METHOD 4: Chartink Scanner (Alternative)

### Setup on Chartink.com (Free):

1. Go to chartink.com → Screener
2. Create New Scan
3. Add Conditions:

```
[Price] [= crossing below] [Bollinger Lower Band (20, 2)]
AND
[RSI (14)] [<] [35]
AND
[Price] [>] [SMA (200)]
AND
[Volume] [<] [SMA of Volume (10)]
AND
[Close] [>] [Open]  // Bullish candle
AND
[Market Cap] [>] [5000]  // Cr
AND
[Avg Volume] [>] [10000000]  // ₹1 Cr+
```

4. Save scan → Run daily at 3:45 PM (after market)

---

## QUICK REFERENCE: What to Look For

### Valid Entry (ALL Green):
```
✅ Price at lower Bollinger Band
✅ RSI(14) below 35
✅ Price above 200-day SMA
✅ Volume declining
✅ Reversal candle (Hammer/Engulfing)
✅ 20 SMA flat
⬜ VIX < 18 (check manually)
⬜ No events in 3 days (check manually)
```

### INVALID Entry (Any Red):
```
❌ Price at upper band (like Ajanta Pharma today)
❌ RSI above 35 (overbought)
❌ Price below 200 SMA (downtrend)
❌ Volume rising (selling pressure)
❌ No reversal candle
❌ 20 SMA sloping down (trend)
```

---

## DAILY SCANNING ROUTINE

```
3:45 PM — Market closes
3:50 PM — Open TradingView/Chartink screener
3:55 PM — Check results against 8-criteria checklist
4:00 PM — Manually verify VIX level (< 18?)
4:05 PM — Check events calendar for matched stocks
4:10 PM — Add valid setups to watchlist_tracker.csv
4:15 PM — Set price alerts for entry zones
4:20 PM — Plan next day's entries
```

---

## EXPECTED RESULTS

| Market Condition | Expected Matches |
|------------------|------------------|
| Range-bound (VIX < 15) | 3-8 stocks/day |
| Mild correction (VIX 15-18) | 5-12 stocks/day |
| Sharp correction (VIX > 18) | 10-20 stocks/day |
| Strong uptrend (VIX < 13) | 0-2 stocks/day |

**Current market (VIX 11.45):** Expect 0-2 matches — market is trending up, few oversold stocks.

---

*Created: Aug 18, 2026*
*Run daily after market close*
*Only trade stocks that pass ALL 8 criteria*
