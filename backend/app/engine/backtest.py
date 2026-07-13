"""
BACKTEST ENGINE
================
Replays historical OHLCV data through the SHARED signal engine.
Uses the SAME signal generation code as the live/paper engine.
No duplicated indicator logic.

Simulates:
- Signal generation (via engine.signals — shared module)
- Fills, stop-loss hits, take-profit hits
- Position sizing via the risk engine formula
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.engine.signals import (
    generate_signal,
    StrategyParams,
    Signal,
)
from app.engine.risk import (
    calculate_stop_loss,
    calculate_take_profit,
    calculate_position_size,
)
from app.database import get_supabase

logger = logging.getLogger(__name__)


@dataclass
class SimulatedTrade:
    """A simulated trade from backtesting."""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    pnl: float
    entry_time: datetime
    exit_time: datetime
    exit_reason: str  # 'stop_loss', 'take_profit', 'signal_exit', 'end_of_data'


@dataclass
class BacktestOutput:
    """Aggregated backtest results."""
    symbol: str
    period_start: str
    period_end: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_r_multiple: float
    profit_factor: float
    max_drawdown_pct: float
    total_pnl: float
    trades: list[SimulatedTrade] = field(default_factory=list)


def run_backtest(
    df: pd.DataFrame,
    symbol: str,
    params: StrategyParams = None,
    initial_equity: float = 100000.0,
    risk_pct: float = 1.0,
    atr_sl_multiplier: float = 2.0,
    atr_tp_multiplier: float = 3.0,
) -> BacktestOutput:
    """
    Run a full backtest on historical OHLCV data.

    Uses the SHARED signal engine (generate_signal) — same code as live.
    No duplicated indicator logic.
    """
    if params is None:
        params = StrategyParams()

    min_bars = max(params.ma_long, params.macd_slow) + 10
    trades: list[SimulatedTrade] = []
    equity = initial_equity
    peak_equity = initial_equity
    max_drawdown_pct = 0.0

    # Track open position
    in_position = False
    position_side = ""
    position_entry = 0.0
    position_qty = 0.0
    position_sl = 0.0
    position_tp = 0.0
    position_entry_time = None

    for i in range(min_bars, len(df)):
        window = df.iloc[: i + 1]
        current_bar = df.iloc[i]
        current_time = df.index[i] if isinstance(df.index[i], datetime) else datetime.now(timezone.utc)

        # Check stop-loss / take-profit for open position
        if in_position:
            hit_sl = False
            hit_tp = False

            if position_side == "buy":
                hit_sl = current_bar["low"] <= position_sl
                hit_tp = current_bar["high"] >= position_tp
            else:
                hit_sl = current_bar["high"] >= position_sl
                hit_tp = current_bar["low"] <= position_tp

            if hit_sl:
                pnl = (position_sl - position_entry) * position_qty
                if position_side == "sell":
                    pnl = (position_entry - position_sl) * position_qty

                equity += pnl
                trades.append(
                    SimulatedTrade(
                        symbol=symbol,
                        side=position_side,
                        entry_price=position_entry,
                        exit_price=position_sl,
                        quantity=position_qty,
                        stop_loss=position_sl,
                        take_profit=position_tp,
                        pnl=pnl,
                        entry_time=position_entry_time,
                        exit_time=current_time,
                        exit_reason="stop_loss",
                    )
                )
                in_position = False
                continue

            if hit_tp:
                pnl = (position_tp - position_entry) * position_qty
                if position_side == "sell":
                    pnl = (position_entry - position_tp) * position_qty

                equity += pnl
                trades.append(
                    SimulatedTrade(
                        symbol=symbol,
                        side=position_side,
                        entry_price=position_entry,
                        exit_price=position_tp,
                        quantity=position_qty,
                        stop_loss=position_sl,
                        take_profit=position_tp,
                        pnl=pnl,
                        entry_time=position_entry_time,
                        exit_time=current_time,
                        exit_reason="take_profit",
                    )
                )
                in_position = False
                continue

        # Generate signal using SHARED engine
        signal = generate_signal(window, symbol, params)

        # Handle exit signal (opposite direction)
        if in_position and signal.direction != "hold":
            if (position_side == "buy" and signal.direction == "sell") or \
               (position_side == "sell" and signal.direction == "buy"):
                exit_price = current_bar["close"]
                if position_side == "buy":
                    pnl = (exit_price - position_entry) * position_qty
                else:
                    pnl = (position_entry - exit_price) * position_qty

                equity += pnl
                trades.append(
                    SimulatedTrade(
                        symbol=symbol,
                        side=position_side,
                        entry_price=position_entry,
                        exit_price=exit_price,
                        quantity=position_qty,
                        stop_loss=position_sl,
                        take_profit=position_tp,
                        pnl=pnl,
                        entry_time=position_entry_time,
                        exit_time=current_time,
                        exit_reason="signal_exit",
                    )
                )
                in_position = False

        # Open new position if not in one
        if not in_position and signal.direction in ("buy", "sell") and signal.confidence >= 2:
            entry_price = current_bar["close"]
            atr = signal.atr if signal.atr > 0 else entry_price * 0.02

            sl = calculate_stop_loss(entry_price, atr, signal.direction, atr_sl_multiplier)
            tp = calculate_take_profit(entry_price, atr, signal.direction, atr_tp_multiplier)
            qty = calculate_position_size(equity, risk_pct, entry_price, sl)

            if qty > 0:
                in_position = True
                position_side = signal.direction
                position_entry = entry_price
                position_qty = qty
                position_sl = sl
                position_tp = tp
                position_entry_time = current_time

        # Track drawdown
        peak_equity = max(peak_equity, equity)
        if peak_equity > 0:
            current_dd = ((peak_equity - equity) / peak_equity) * 100
            max_drawdown_pct = max(max_drawdown_pct, current_dd)

    # Close any remaining position at end of data
    if in_position:
        exit_price = df.iloc[-1]["close"]
        exit_time = df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now(timezone.utc)

        if position_side == "buy":
            pnl = (exit_price - position_entry) * position_qty
        else:
            pnl = (position_entry - exit_price) * position_qty

        equity += pnl
        trades.append(
            SimulatedTrade(
                symbol=symbol,
                side=position_side,
                entry_price=position_entry,
                exit_price=exit_price,
                quantity=position_qty,
                stop_loss=position_sl,
                take_profit=position_tp,
                pnl=pnl,
                entry_time=position_entry_time,
                exit_time=exit_time,
                exit_reason="end_of_data",
            )
        )

    # Calculate aggregate metrics
    total_trades = len(trades)
    winning = [t for t in trades if t.pnl > 0]
    losing = [t for t in trades if t.pnl <= 0]

    win_rate = (len(winning) / total_trades * 100) if total_trades > 0 else 0.0

    total_profit = sum(t.pnl for t in winning)
    total_loss = abs(sum(t.pnl for t in losing))
    profit_factor = (total_profit / total_loss) if total_loss > 0 else (
        float("inf") if total_profit > 0 else 0.0
    )

    # Average R-multiple
    r_multiples = []
    for t in trades:
        risk_per_trade = abs(t.entry_price - t.stop_loss) * t.quantity
        if risk_per_trade > 0:
            r_multiples.append(t.pnl / risk_per_trade)
    avg_r = np.mean(r_multiples) if r_multiples else 0.0

    period_start = str(df.index[0].date()) if hasattr(df.index[0], "date") else str(df.index[0])
    period_end = str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1])

    return BacktestOutput(
        symbol=symbol,
        period_start=period_start,
        period_end=period_end,
        total_trades=total_trades,
        winning_trades=len(winning),
        losing_trades=len(losing),
        win_rate=round(win_rate, 2),
        avg_r_multiple=round(float(avg_r), 3),
        profit_factor=round(profit_factor, 3) if profit_factor != float("inf") else 999.0,
        max_drawdown_pct=round(max_drawdown_pct, 2),
        total_pnl=round(equity - initial_equity, 2),
        trades=trades,
    )


def save_backtest_result(
    result: BacktestOutput,
    strategy_config_id: str = None,
) -> dict:
    """Save backtest results to Supabase."""
    db = get_supabase()
    record = {
        "symbol": result.symbol,
        "strategy_config_id": strategy_config_id,
        "period_start": result.period_start,
        "period_end": result.period_end,
        "total_trades": result.total_trades,
        "win_rate": result.win_rate,
        "avg_r_multiple": result.avg_r_multiple,
        "profit_factor": result.profit_factor,
        "max_drawdown_pct": result.max_drawdown_pct,
    }
    response = db.table("backtest_results").insert(record).execute()
    return response.data[0] if response.data else record
