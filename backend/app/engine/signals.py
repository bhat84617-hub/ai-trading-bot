"""
SHARED SIGNAL ENGINE — THE SINGLE SOURCE OF TRUTH
===================================================
This module is used by:
  1. Live/Paper scan cycle
  2. Backtest engine
  3. Walk-forward validation engine

DO NOT duplicate indicator logic elsewhere. All signal generation
flows through this module.

Indicators: RSI, MACD, Moving Average Crossover, Volume Spike
Regime Detection: ADX-based (trending vs ranging)
Confirmation: Signal fires ONLY when 2+ regime-appropriate indicators agree
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Data Structures ───────────────────────────────────────────────────

@dataclass
class IndicatorValues:
    """Raw indicator output values."""
    rsi: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    ma_short: Optional[float] = None
    ma_long: Optional[float] = None
    volume_sma: Optional[float] = None
    current_volume: Optional[float] = None
    adx: Optional[float] = None
    close: Optional[float] = None


@dataclass
class Signal:
    """Signal output from the engine."""
    symbol: str
    direction: str  # 'buy', 'sell', 'hold'
    regime: str  # 'trending', 'ranging'
    confirming_indicators: list[str] = field(default_factory=list)
    indicator_values: dict = field(default_factory=dict)
    confidence: int = 0  # count of confirming indicators (0-4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    atr: float = 0.0  # for stop-loss calculation


@dataclass
class StrategyParams:
    """Strategy configuration parameters."""
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    ma_short: int = 20
    ma_long: int = 50
    adx_period: int = 14
    adx_trending_threshold: float = 25.0
    volume_spike_multiplier: float = 1.5
    atr_period: int = 14


# ── Indicator Calculations ────────────────────────────────────────────

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute Relative Strength Index."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute MACD line, signal line, and histogram."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_moving_averages(
    close: pd.Series,
    short_period: int = 20,
    long_period: int = 50,
) -> tuple[pd.Series, pd.Series]:
    """Compute short and long simple moving averages."""
    ma_short = close.rolling(window=short_period).mean()
    ma_long = close.rolling(window=long_period).mean()
    return ma_short, ma_long


def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Compute Average Directional Index for regime detection.
    ADX > threshold = trending, ADX <= threshold = ranging.
    """
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr = true_range.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)

    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.ewm(span=period, adjust=False).mean()

    return adx


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Compute Average True Range for stop-loss distance."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    return atr


def compute_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Compute volume simple moving average for spike detection."""
    return volume.rolling(window=period).mean()


# ── Regime Detection ──────────────────────────────────────────────────

def detect_regime(adx_value: float, threshold: float = 25.0) -> str:
    """
    Classify market regime based on ADX value.
    ADX > threshold → trending (trend-following rules apply)
    ADX <= threshold → ranging (mean-reversion rules apply)
    """
    if adx_value is None or np.isnan(adx_value):
        return "ranging"  # default to ranging if ADX unavailable
    return "trending" if adx_value > threshold else "ranging"


# ── Signal Generation (THE CORE LOGIC) ────────────────────────────────

def generate_signal(
    df: pd.DataFrame,
    symbol: str,
    params: StrategyParams = None,
) -> Signal:
    """
    Generate a trading signal for a symbol given OHLCV data.

    This is THE function that backtest, walk-forward, and live scan ALL call.
    DO NOT duplicate this logic.

    Rules:
    - Detect regime (trending vs ranging) via ADX
    - In TRENDING regime: apply trend-following indicators
      (MA crossover, MACD momentum, RSI trend confirmation)
    - In RANGING regime: apply mean-reversion indicators
      (RSI overbought/oversold, MACD divergence, volume spike)
    - Signal fires ONLY if 2+ applicable indicators agree
    """
    if params is None:
        params = StrategyParams()

    if len(df) < max(params.ma_long, params.macd_slow) + 10:
        return Signal(
            symbol=symbol,
            direction="hold",
            regime="unknown",
            confirming_indicators=[],
            indicator_values={},
            confidence=0,
        )

    # Compute all indicators
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    rsi = compute_rsi(close, params.rsi_period)
    macd_line, macd_signal_line, macd_hist = compute_macd(
        close, params.macd_fast, params.macd_slow, params.macd_signal
    )
    ma_short, ma_long = compute_moving_averages(
        close, params.ma_short, params.ma_long
    )
    adx = compute_adx(high, low, close, params.adx_period)
    atr = compute_atr(high, low, close, params.atr_period)
    vol_sma = compute_volume_sma(volume)

    # Get latest values
    latest_rsi = rsi.iloc[-1]
    latest_macd = macd_line.iloc[-1]
    latest_macd_signal = macd_signal_line.iloc[-1]
    latest_macd_hist = macd_hist.iloc[-1]
    prev_macd_hist = macd_hist.iloc[-2] if len(macd_hist) > 1 else 0
    latest_ma_short = ma_short.iloc[-1]
    latest_ma_long = ma_long.iloc[-1]
    prev_ma_short = ma_short.iloc[-2] if len(ma_short) > 1 else latest_ma_short
    prev_ma_long = ma_long.iloc[-2] if len(ma_long) > 1 else latest_ma_long
    latest_adx = adx.iloc[-1]
    latest_atr = atr.iloc[-1]
    latest_volume = volume.iloc[-1]
    latest_vol_sma = vol_sma.iloc[-1]
    latest_close = close.iloc[-1]

    indicator_vals = IndicatorValues(
        rsi=latest_rsi,
        macd_line=latest_macd,
        macd_signal=latest_macd_signal,
        macd_histogram=latest_macd_hist,
        ma_short=latest_ma_short,
        ma_long=latest_ma_long,
        volume_sma=latest_vol_sma,
        current_volume=latest_volume,
        adx=latest_adx,
        close=latest_close,
    )

    # Detect regime
    regime = detect_regime(latest_adx, params.adx_trending_threshold)

    buy_signals: list[str] = []
    sell_signals: list[str] = []

    if regime == "trending":
        # ── Trend-Following Rules ──

        # 1. MA Crossover (bullish: short crosses above long)
        if latest_ma_short > latest_ma_long and prev_ma_short <= prev_ma_long:
            buy_signals.append("ma_crossover_bullish")
        elif latest_ma_short < latest_ma_long and prev_ma_short >= prev_ma_long:
            sell_signals.append("ma_crossover_bearish")

        # 2. MACD Momentum (bullish: histogram turns positive)
        if latest_macd_hist > 0 and prev_macd_hist <= 0:
            buy_signals.append("macd_bullish_momentum")
        elif latest_macd_hist < 0 and prev_macd_hist >= 0:
            sell_signals.append("macd_bearish_momentum")

        # 3. RSI Trend Confirmation (not overbought for buys, not oversold for sells)
        if 40 < latest_rsi < params.rsi_overbought:
            buy_signals.append("rsi_trend_confirm_buy")
        elif params.rsi_oversold < latest_rsi < 60:
            sell_signals.append("rsi_trend_confirm_sell")

        # 4. Volume Spike Confirmation
        if latest_vol_sma and latest_vol_sma > 0:
            if latest_volume > latest_vol_sma * params.volume_spike_multiplier:
                if latest_close > close.iloc[-2]:
                    buy_signals.append("volume_spike_bullish")
                else:
                    sell_signals.append("volume_spike_bearish")

    else:
        # ── Mean-Reversion Rules (Ranging Regime) ──

        # 1. RSI Overbought/Oversold
        if latest_rsi <= params.rsi_oversold:
            buy_signals.append("rsi_oversold")
        elif latest_rsi >= params.rsi_overbought:
            sell_signals.append("rsi_overbought")

        # 2. MACD Divergence (histogram reversal)
        if latest_macd_hist > 0 and prev_macd_hist <= 0:
            buy_signals.append("macd_reversal_bullish")
        elif latest_macd_hist < 0 and prev_macd_hist >= 0:
            sell_signals.append("macd_reversal_bearish")

        # 3. Price near MA support/resistance
        ma_mid = (latest_ma_short + latest_ma_long) / 2
        if latest_close < ma_mid * 0.98:  # below support
            buy_signals.append("price_below_ma_support")
        elif latest_close > ma_mid * 1.02:  # above resistance
            sell_signals.append("price_above_ma_resistance")

        # 4. Volume Spike (reversal confirmation)
        if latest_vol_sma and latest_vol_sma > 0:
            if latest_volume > latest_vol_sma * params.volume_spike_multiplier:
                if latest_rsi <= params.rsi_oversold + 10:
                    buy_signals.append("volume_spike_reversal_buy")
                elif latest_rsi >= params.rsi_overbought - 10:
                    sell_signals.append("volume_spike_reversal_sell")

    # ── Confirmation Gate: 2+ indicators must agree ──
    indicator_dict = {
        "rsi": float(latest_rsi) if not np.isnan(latest_rsi) else None,
        "macd_line": float(latest_macd) if not np.isnan(latest_macd) else None,
        "macd_signal": float(latest_macd_signal) if not np.isnan(latest_macd_signal) else None,
        "macd_histogram": float(latest_macd_hist) if not np.isnan(latest_macd_hist) else None,
        "ma_short": float(latest_ma_short) if not np.isnan(latest_ma_short) else None,
        "ma_long": float(latest_ma_long) if not np.isnan(latest_ma_long) else None,
        "adx": float(latest_adx) if not np.isnan(latest_adx) else None,
        "atr": float(latest_atr) if not np.isnan(latest_atr) else None,
        "volume": float(latest_volume) if not np.isnan(latest_volume) else None,
        "volume_sma": float(latest_vol_sma) if latest_vol_sma and not np.isnan(latest_vol_sma) else None,
        "close": float(latest_close),
    }

    if len(buy_signals) >= 2:
        return Signal(
            symbol=symbol,
            direction="buy",
            regime=regime,
            confirming_indicators=buy_signals,
            indicator_values=indicator_dict,
            confidence=len(buy_signals),
            atr=float(latest_atr) if not np.isnan(latest_atr) else 0.0,
        )
    elif len(sell_signals) >= 2:
        return Signal(
            symbol=symbol,
            direction="sell",
            regime=regime,
            confirming_indicators=sell_signals,
            indicator_values=indicator_dict,
            confidence=len(sell_signals),
            atr=float(latest_atr) if not np.isnan(latest_atr) else 0.0,
        )
    else:
        return Signal(
            symbol=symbol,
            direction="hold",
            regime=regime,
            confirming_indicators=buy_signals + sell_signals,
            indicator_values=indicator_dict,
            confidence=max(len(buy_signals), len(sell_signals)),
            atr=float(latest_atr) if not np.isnan(latest_atr) else 0.0,
        )


def generate_signals_for_dataframe(
    df: pd.DataFrame,
    symbol: str,
    params: StrategyParams = None,
) -> list[Signal]:
    """
    Generate signals for each bar in the DataFrame (used by backtest).
    Processes the df in a rolling window fashion.
    """
    if params is None:
        params = StrategyParams()

    min_bars = max(params.ma_long, params.macd_slow) + 10
    signals = []

    for i in range(min_bars, len(df)):
        window = df.iloc[:i + 1]
        signal = generate_signal(window, symbol, params)
        signal.timestamp = df.index[i] if isinstance(df.index[i], datetime) else datetime.now(timezone.utc)
        signals.append(signal)

    return signals
