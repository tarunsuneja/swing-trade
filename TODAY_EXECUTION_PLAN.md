# BROKER ORDER TEMPLATES — Aug 18, 2026
## Execute these orders in your broker (Zerodha/Angel One/Upstox)

---

## ORDER 1: AJANTA PHARMA (BUY)

### Step 1: Entry Order
```
Stock:          AJANTPHARM (Ajanta Pharma)
Exchange:       NSE
Action:         BUY
Product:        CNC (Delivery) or MIS (Intraday — if you want to avoid delivery)
Order Type:     LIMIT
Quantity:       60 shares
Price:          ₹3,780 (limit order — slightly below CMP)
Validity:       DAY
Disclosed Qty:  60

After Fill:     Set GTT Stop Loss immediately
```

### Step 2: Stop Loss Order (Set IMMEDIATELY after entry fill)
```
Stock:          AJANTPHARM
Exchange:       NSE
Action:         SELL
Product:        CNC or MIS
Order Type:     SL (Stop Loss Limit)
Quantity:       60 shares
Trigger Price:  ₹3,660
Price:          ₹3,650 (limit slightly below trigger)
Validity:       GTT (Good Till Triggered)
```

### Step 3: Target Order (Set after entry)
```
Stock:          AJANTPHARM
Exchange:       NSE
Action:         SELL
Product:        CNC or MIS
Order Type:     LIMIT
Quantity:       30 shares (50% at T1)
Price:          ₹3,950
Validity:       GTT

Second Target:
Quantity:       30 shares (remaining 50%)
Price:          ₹4,150
Validity:       GTT
```

### Trade Summary
| Parameter | Value |
|-----------|-------|
| Entry Price | ₹3,780 |
| Quantity | 60 shares |
| Total Investment | ₹2,26,800 |
| Stop Loss | ₹3,650 |
| Risk per Share | ₹130 |
| Total Risk | ₹7,800 (0.52% of ₹15L) |
| Target 1 | ₹3,950 (₹10,200 profit) |
| Target 2 | ₹4,150 (₹22,200 profit) |
| Risk:Reward T1 | 1:1.3 |
| Risk:Reward T2 | 1:2.8 |

---

## ORDER 2: MARKSANS PHARMA (BUY)

### Step 1: Entry Order
```
Stock:          MARKSANS (Marksans Pharma)
Exchange:       NSE
Action:         BUY
Product:        CNC (Delivery) or MIS
Order Type:     LIMIT
Quantity:       600 shares
Price:          ₹308 (limit order)
Validity:       DAY
Disclosed Qty:  600

After Fill:     Set GTT Stop Loss immediately
```

### Step 2: Stop Loss Order (Set IMMEDIATELY after entry fill)
```
Stock:          MARKSANS
Exchange:       NSE
Action:         SELL
Product:        CNC or MIS
Order Type:     SL (Stop Loss Limit)
Quantity:       600 shares
Trigger Price:  ₹296
Price:          ₹295 (limit slightly below trigger)
Validity:       GTT
```

### Step 3: Target Order (Set after entry)
```
Stock:          MARKSANS
Exchange:       NSE
Action:         SELL
Product:        CNC or MIS
Order Type:     LIMIT
Quantity:       300 shares (50% at T1)
Price:          ₹335
Validity:       GTT

Second Target:
Quantity:       300 shares (remaining 50%)
Price:          ₹360
Validity:       GTT
```

### Trade Summary
| Parameter | Value |
|-----------|-------|
| Entry Price | ₹308 |
| Quantity | 600 shares |
| Total Investment | ₹1,84,800 |
| Stop Loss | ₹295 |
| Risk per Share | ₹13 |
| Total Risk | ₹7,800 (0.52% of ₹15L) |
| Target 1 | ₹335 (₹16,200 profit) |
| Target 2 | ₹360 (₹31,200 profit) |
| Risk:Reward T1 | 1:2.1 |
| Risk:Reward T2 | 1:4.0 |

---

## PORTFOLIO SUMMARY

| Stock | Entry | Qty | Investment | Stop | Risk | T1 | T2 |
|-------|-------|-----|------------|------|------|----|----|
| Ajanta Pharma | ₹3,780 | 60 | ₹2,26,800 | ₹3,650 | ₹7,800 | ₹3,950 | ₹4,150 |
| Marksans Pharma | ₹308 | 600 | ₹1,84,800 | ₹295 | ₹7,800 | ₹335 | ₹360 |
| **TOTAL** | | | **₹4,11,600** | | **₹15,600** | | |

| Metric | Value | Limit | Status |
|--------|-------|-------|--------|
| Capital Deployed | ₹4,11,600 | ₹12,00,000 | ✅ 34% |
| Total Risk | ₹15,600 | ₹22,500 (1.5%) | ✅ 1.04% |
| Cash Reserve | ₹10,88,400 | ₹3,00,000 (20%) | ✅ 73% |
| Positions | 2 | 6-8 | ✅ |

---

## EXECUTION SEQUENCE

```
9:15 AM — Market opens. DO NOT enter in first 15 minutes.
9:30 AM — Check if Ajanta Pharma is holding above ₹3,750
9:35 AM — If yes, place BUY limit order at ₹3,780
9:40 AM — Check if Marksans Pharma is holding above ₹305
9:45 AM — If yes, place BUY limit order at ₹308
10:00 AM — After fills, IMMEDIATELY set stop loss GTT orders
10:05 AM — Set target GTT orders (T1 and T2)
10:10 AM — Update trading_journal.csv and open_positions.csv
11:00 AM — Monitor. Trail stop to cost if up 1.5x risk.
2:30 PM — No new entries after this time.
3:30 PM — Journal review. Plan tomorrow.
```

---

## EMERGENCY PROTOCOL

### If Stop Loss Hits
```
1. Accept the loss — don't move the stop
2. Log in trading_journal.csv
3. Do NOT re-enter same stock for 3 days
4. Reduce next position size by 25%
5. Review: Was the setup valid? Did you follow rules?
```

### If Market Crashes (Nifty -2%+)
```
1. Check all open positions
2. If any position is down > 5%, consider closing
3. DO NOT average down
4. Close all positions if total portfolio down > 3%
5. Wait for VIX to stabilize before re-entering
```

### If VIX Spikes Above 18
```
1. Reduce position sizes by 50%
2. Tighten stops to 1x ATR (from 1.5x)
3. No new entries until VIX below 16
4. Consider protective puts on existing positions
```

---

## IMPORTANT REMINDERS

1. **Always use LIMIT orders** — never market orders
2. **Set stop loss IMMEDIATELY** after entry — no mental stops
3. **Do NOT move stops against you**
4. **Trail stop to cost** once trade is up 1.5x risk
5. **Book 50% at T1** — let rest run to T2
6. **Journal every trade** — win or lose
7. **No revenge trading** — if stop hits, walk away

---

*Execution plan created: Aug 18, 2026*
*Execute in sequence. Follow rules. No exceptions.*
