"""
SWING TRADING BACKTESTER — Starter Script for Indian Market (NSE)
Target: ₹1L/month from ₹15L capital
Author: PortfolioTracker | Date: Aug 2026

Requirements:
    pip install yfinance pandas numpy ta backtrader matplotlib

Usage:
    python backtest_starter.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
import ta
import backtrader as bt
import matplotlib.pyplot as plt
from datetime import datetime, timedelta


# =============================================================================
# SECTION 1: DATA DOWNLOAD
# =============================================================================

def download_nse_data(symbol, period="5y"):
    """Download NSE stock data from Yahoo Finance."""
    ticker = f"{symbol}.NS"
    df = yf.download(ticker, period=period, interval="1d")
    df.dropna(inplace=True)
    print(f"Downloaded {symbol}: {len(df)} bars from {df.index[0].date()} to {df.index[-1].date()}")
    return df


# =============================================================================
# SECTION 2: TECHNICAL INDICATORS
# =============================================================================

def add_indicators(df):
    """Add all technical indicators needed for strategies."""
    # Moving Averages
    df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
    df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50)
    df['SMA_200'] = ta.trend.sma_indicator(df['Close'], window=200)
    df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)

    # RSI
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)

    # MACD
    macd = ta.trend.MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Hist'] = macd.macd_diff()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df['Close'], window=20, window_dev=2)
    df['BB_Upper'] = bb.bollinger_hband()
    df['BB_Lower'] = bb.bollinger_lband()
    df['BB_Mid'] = bb.bollinger_mavg()
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Mid']

    # ATR
    df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)

    # ADX
    df['ADX'] = ta.trend.adx(df['High'], df['Low'], df['Close'], window=14)

    # Supertrend (simplified)
    df['Supertrend'] = df['Close']  # Placeholder - use ta-lib for proper supertrend

    # Volume
    df['Volume_SMA_20'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA_20']

    # Delivery percentage placeholder (not available via yfinance)
    df['Delivery_Pct'] = 50  # Placeholder

    return df


# =============================================================================
# SECTION 3: STRATEGY IMPLEMENTATIONS
# =============================================================================

class BollingerBandStrategy(bt.Strategy):
    """Bollinger Band Mean Reversion Strategy."""
    params = (
        ('rsi_buy', 35),
        ('rsi_sell', 65),
        ('risk_pct', 0.015),  # 1.5% risk per trade
        ('atr_stop_mult', 1.5),
    )

    def __init__(self):
        self.rsi = ta.momentum.rsi(self.data.close, window=14)
        self.bb_mid = ta.volatility.bollinger_mavg(self.data.close, window=20)
        self.bb_upper = ta.volatility.bollinger_hband(self.data.close, window=20, window_dev=2)
        self.bb_lower = ta.volatility.bollinger_lband(self.data.close, window=20, window_dev=2)
        self.sma_200 = ta.trend.sma_indicator(self.data.close, window=200)
        self.atr = ta.volatility.average_true_range(self.data.high, self.data.low, self.data.close, window=14)
        self.order = None
        self.entry_price = None
        self.stop_price = None

    def next(self):
        if self.order:
            return

        if not self.position:
            # Entry: Price touches lower BB + RSI oversold + above 200 SMA
            if (self.data.close[0] <= self.bb_lower[0] and
                self.rsi[0] < self.params.rsi_buy and
                self.sma_200[0] and self.data.close[0] > self.sma_200[0]):

                # Position sizing: risk 1.5% of capital
                risk_amount = self.broker.getvalue() * self.params.risk_pct
                stop_distance = self.atr[0] * self.params.atr_stop_mult
                shares = int(risk_amount / stop_distance)

                if shares > 0:
                    self.entry_price = self.data.close[0]
                    self.stop_price = self.entry_price - stop_distance
                    self.order = self.buy(size=shares)
        else:
            # Exit: Price reaches middle BB or hits stop
            if self.data.close[0] >= self.bb_mid[0]:
                self.order = self.sell(size=self.position.size)
            elif self.data.close[0] <= self.stop_price:
                self.order = self.sell(size=self.position.size)


class MomentumBreakoutStrategy(bt.Strategy):
    """Volume Breakout Strategy."""
    params = (
        ('consolidation_days', 10),
        ('volume_mult', 1.5),
        ('risk_pct', 0.015),
        ('atr_stop_mult', 2.0),
    )

    def __init__(self):
        self.sma_50 = ta.trend.sma_indicator(self.data.close, window=50)
        self.sma_200 = ta.trend.sma_indicator(self.data.close, window=200)
        self.atr = ta.volatility.average_true_range(self.data.high, self.data.low, self.data.close, window=14)
        self.vol_sma = self.data.volume.rolling(window=20).mean()
        self.order = None
        self.entry_price = None
        self.stop_price = None

    def next(self):
        if self.order:
            return

        if not self.position:
            # Check consolidation (simplified)
            high_10 = max(self.data.high.get(ago=-1, size=self.params.consolidation_days))
            low_10 = min(self.data.low.get(ago=-1, size=self.params.consolidation_days))
            range_pct = (high_10 - low_10) / low_10 * 100

            # Breakout conditions
            if (range_pct < 12 and  # Consolidation range
                self.data.close[0] > high_10 and  # Breakout above range
                self.data.volume[0] > self.vol_sma[0] * self.params.volume_mult and  # Volume confirmation
                self.sma_200[0] and self.data.close[0] > self.sma_200[0]):  # Above 200 SMA

                risk_amount = self.broker.getvalue() * self.params.risk_pct
                stop_distance = self.atr[0] * self.params.atr_stop_mult
                shares = int(risk_amount / stop_distance)

                if shares > 0:
                    self.entry_price = self.data.close[0]
                    self.stop_price = self.entry_price - stop_distance
                    self.order = self.buy(size=shares)
        else:
            # Exit: Target 2x risk or stop loss
            if self.entry_price:
                target = self.entry_price + (self.entry_price - self.stop_price) * 2
                if self.data.close[0] >= target or self.data.close[0] <= self.stop_price:
                    self.order = self.sell(size=self.position.size)


class RSIDivergenceStrategy(bt.Strategy):
    """RSI Divergence Strategy (Simplified)."""
    params = (
        ('rsi_buy', 30),
        ('rsi_sell', 70),
        ('risk_pct', 0.015),
    )

    def __init__(self):
        self.rsi = ta.momentum.rsi(self.data.close, window=14)
        self.sma_200 = ta.trend.sma_indicator(self.data.close, window=200)
        self.atr = ta.volatility.average_true_range(self.data.high, self.data.low, self.data.close, window=14)
        self.order = None
        self.entry_price = None
        self.stop_price = None

    def next(self):
        if self.order:
            return

        if not self.position:
            # Simplified divergence: Price makes lower low but RSI makes higher low
            if (self.rsi[0] < self.params.rsi_buy and
                self.sma_200[0] and self.data.close[0] > self.sma_200[0]):

                risk_amount = self.broker.getvalue() * self.params.risk_pct
                stop_distance = self.atr[0] * 2
                shares = int(risk_amount / stop_distance)

                if shares > 0:
                    self.entry_price = self.data.close[0]
                    self.stop_price = self.entry_price - stop_distance
                    self.order = self.buy(size=shares)
        else:
            # Exit: RSI overbought or stop loss
            if self.rsi[0] > self.params.rsi_sell or self.data.close[0] <= self.stop_price:
                self.order = self.sell(size=self.position.size)


# =============================================================================
# SECTION 4: BACKTESTING ENGINE
# =============================================================================

def run_backtest(df, strategy_class, initial_cash=1500000, commission=0.001):
    """Run backtest with given strategy."""
    cerebro = bt.Cerebro()

    # Add strategy
    cerebro.addstrategy(strategy_class)

    # Add data
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    # Set broker settings
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)

    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', timeframe=bt.TimeFrame.Days, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    # Run
    print(f"\n{'='*60}")
    print(f"Starting Portfolio Value: ₹{cerebro.broker.getvalue():,.2f}")
    print(f"{'='*60}")

    results = cerebro.run()
    strat = results[0]

    # Print results
    print(f"\n{'='*60}")
    print(f"FINAL PORTFOLIO VALUE: ₹{cerebro.broker.getvalue():,.2f}")
    print(f"{'='*60}")

    # Sharpe Ratio
    sharpe = strat.analyzers.sharpe.get_analysis()
    sharpe_ratio = sharpe.get('sharperatio', None)
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}" if sharpe_ratio else "Sharpe Ratio: N/A")

    # Drawdown
    dd = strat.analyzers.drawdown.get_analysis()
    print(f"Max Drawdown: {dd.get('max', {}).get('drawdown', 0):.2f}%")
    print(f"Max Drawdown Length: {dd.get('max', {}).get('len', 0)} days")

    # Trade Analysis
    trades = strat.analyzers.trades.get_analysis()
    total_trades = trades.get('total', {}).get('total', 0)
    won = trades.get('won', {}).get('total', 0)
    lost = trades.get('lost', {}).get('total', 0)
    win_rate = (won / total_trades * 100) if total_trades > 0 else 0

    print(f"\nTotal Trades: {total_trades}")
    print(f"Winning Trades: {won}")
    print(f"Losing Trades: {lost}")
    print(f"Win Rate: {win_rate:.1f}%")

    if total_trades > 0:
        avg_win = trades.get('won', {}).get('pnl', {}).get('average', 0)
        avg_loss = trades.get('lost', {}).get('pnl', {}).get('average', 0)
        print(f"Average Win: ₹{avg_win:,.2f}")
        print(f"Average Loss: ₹{abs(avg_loss):,.2f}")
        if avg_loss != 0:
            print(f"Risk:Reward Ratio: 1:{abs(avg_win/avg_loss):.1f}")

    return results


# =============================================================================
# SECTION 5: VISUALIZATION
# =============================================================================

def plot_results(df, strategy_class, title="Backtest Results"):
    """Plot backtest results with indicators."""
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)

    # Price and indicators
    axes[0].plot(df.index, df['Close'], label='Close', linewidth=1)
    axes[0].plot(df.index, df['SMA_20'], label='SMA 20', alpha=0.7)
    axes[0].plot(df.index, df['SMA_50'], label='SMA 50', alpha=0.7)
    axes[0].plot(df.index, df['BB_Upper'], label='BB Upper', alpha=0.5, linestyle='--')
    axes[0].plot(df.index, df['BB_Lower'], label='BB Lower', alpha=0.5, linestyle='--')
    axes[0].set_ylabel('Price (₹)')
    axes[0].legend()
    axes[0].set_title(title)

    # RSI
    axes[1].plot(df.index, df['RSI'], label='RSI', color='purple')
    axes[1].axhline(y=30, color='g', linestyle='--', alpha=0.5, label='Oversold (30)')
    axes[1].axhline(y=70, color='r', linestyle='--', alpha=0.5, label='Overbought (70)')
    axes[1].set_ylabel('RSI')
    axes[1].legend()
    axes[1].set_ylim(0, 100)

    # Volume
    axes[2].bar(df.index, df['Volume'], color='gray', alpha=0.5)
    axes[2].plot(df.index, df['Volume_SMA_20'], color='blue', label='Vol SMA 20')
    axes[2].set_ylabel('Volume')
    axes[2].legend()

    plt.tight_layout()
    plt.savefig('backtest_results.png', dpi=150, bbox_inches='tight')
    plt.show()
    print("Chart saved as backtest_results.png")


# =============================================================================
# SECTION 6: MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SWING TRADING BACKTESTER — Indian Market (NSE)")
    print("Capital: ₹15,00,000 | Target: ₹1,00,000/month")
    print("=" * 60)

    # Configuration
    SYMBOLS = ["RELIANCE", "HDFCBANK", "INFY", "ICICIBANK", "TCS"]
    STRATEGIES = {
        "Bollinger Band": BollingerBandStrategy,
        "Momentum Breakout": MomentumBreakoutStrategy,
        "RSI Divergence": RSIDivergenceStrategy,
    }

    # Run backtests
    for symbol in SYMBOLS:
        print(f"\n{'#'*60}")
        print(f"# BACKTESTING: {symbol}")
        print(f"{'#'*60}")

        # Download data
        df = download_nse_data(symbol, period="5y")
        df = add_indicators(df)

        # Run each strategy
        for strategy_name, strategy_class in STRATEGIES.items():
            print(f"\n--- Strategy: {strategy_name} ---")
            results = run_backtest(df, strategy_class)

    print("\n" + "=" * 60)
    print("BACKTESTING COMPLETE")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Analyze results across all strategies")
    print("2. Pick the best strategy for each stock")
    print("3. Paper trade for 3 months")
    print("4. Start live with 0.5% risk per trade")
    print("5. Add AI sentiment layer (Month 6)")
