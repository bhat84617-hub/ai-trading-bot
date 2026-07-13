"""
WALK-FORWARD VALIDATION ENGINE
================================
Splits historical data into N rolling windows, runs backtest on each,
and aggregates results. Sets live_eligible = true ONLY if ALL conditions pass:

1. total_trades_across_windows >= min_trades_threshold (default 50)
2. aggregate_profit_factor >= min_profit_factor_threshold (default 1.2)
3. worst_window_drawdown_pct within tolerance

This gate is enforced in the execution engine's code path —
NOT just shown as a UI warning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.engine.backtest import run_backtest, BacktestOutput
from app.engine.signals import StrategyParams
from app.database import get_supabase

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardOutput:
    """Walk-forward validation result."""
    symbol: str
    num_windows: int
    total_trades_across_windows: int
    aggregate_win_rate: float
    aggregate_profit_factor: float
    worst_window_drawdown_pct: float
    passed: bool
    pass_reason: str
    min_trades_threshold: int
    min_profit_factor_threshold: float
    window_results: list[BacktestOutput]


def run_walk_forward(
    df: pd.DataFrame,
    symbol: str,
    num_windows: int = 5,
    params: StrategyParams = None,
    initial_equity: float = 100000.0,
    risk_pct: float = 1.0,
    min_trades_threshold: int = 50,
    min_profit_factor_threshold: float = 1.2,
    max_drawdown_tolerance: float = 25.0,
) -> WalkForwardOutput:
    """
    Run walk-forward validation across N rolling windows.

    Each window uses the SHARED signal engine (via backtest engine).
    No duplicated indicator logic anywhere.
    """
    if params is None:
        params = StrategyParams()

    total_bars = len(df)
    window_size = total_bars // num_windows

    if window_size < max(params.ma_long, params.macd_slow) + 20:
        return WalkForwardOutput(
            symbol=symbol,
            num_windows=num_windows,
            total_trades_across_windows=0,
            aggregate_win_rate=0.0,
            aggregate_profit_factor=0.0,
            worst_window_drawdown_pct=0.0,
            passed=False,
            pass_reason=f"Insufficient data: {total_bars} bars for {num_windows} windows (need ~{(max(params.ma_long, params.macd_slow) + 20) * num_windows} bars)",
            min_trades_threshold=min_trades_threshold,
            min_profit_factor_threshold=min_profit_factor_threshold,
            window_results=[],
        )

    window_results: list[BacktestOutput] = []

    for w in range(num_windows):
        start_idx = w * window_size
        end_idx = start_idx + window_size if w < num_windows - 1 else total_bars
        window_df = df.iloc[start_idx:end_idx]

        if len(window_df) < max(params.ma_long, params.macd_slow) + 10:
            continue

        result = run_backtest(
            df=window_df,
            symbol=symbol,
            params=params,
            initial_equity=initial_equity,
            risk_pct=risk_pct,
        )
        window_results.append(result)

    # Aggregate metrics
    total_trades = sum(r.total_trades for r in window_results)
    total_winning = sum(r.winning_trades for r in window_results)

    agg_win_rate = (total_winning / total_trades * 100) if total_trades > 0 else 0.0

    # Aggregate profit factor
    total_profit = 0.0
    total_loss = 0.0
    for r in window_results:
        for t in r.trades:
            if t.pnl > 0:
                total_profit += t.pnl
            else:
                total_loss += abs(t.pnl)

    agg_profit_factor = (total_profit / total_loss) if total_loss > 0 else (
        999.0 if total_profit > 0 else 0.0
    )

    worst_drawdown = max(
        (r.max_drawdown_pct for r in window_results), default=0.0
    )

    # ── VALIDATION GATE (MANDATORY) ──
    failures = []

    if total_trades < min_trades_threshold:
        failures.append(
            f"Insufficient trades: {total_trades}/{min_trades_threshold} "
            f"(needs {min_trades_threshold - total_trades} more)"
        )

    if agg_profit_factor < min_profit_factor_threshold:
        failures.append(
            f"Profit factor too low: {agg_profit_factor:.3f} "
            f"(minimum {min_profit_factor_threshold})"
        )

    if worst_drawdown > max_drawdown_tolerance:
        failures.append(
            f"Max drawdown exceeded: {worst_drawdown:.2f}% "
            f"(tolerance {max_drawdown_tolerance}%)"
        )

    passed = len(failures) == 0
    pass_reason = "All validation criteria passed" if passed else "; ".join(failures)

    return WalkForwardOutput(
        symbol=symbol,
        num_windows=len(window_results),
        total_trades_across_windows=total_trades,
        aggregate_win_rate=round(agg_win_rate, 2),
        aggregate_profit_factor=round(agg_profit_factor, 3),
        worst_window_drawdown_pct=round(worst_drawdown, 2),
        passed=passed,
        pass_reason=pass_reason,
        min_trades_threshold=min_trades_threshold,
        min_profit_factor_threshold=min_profit_factor_threshold,
        window_results=window_results,
    )


def save_walk_forward_result(
    result: WalkForwardOutput,
    strategy_config_id: str = None,
) -> dict:
    """
    Save walk-forward results to Supabase.
    If passed, also update strategy_config.live_eligible = true.
    """
    db = get_supabase()

    # Save walk-forward result
    record = {
        "symbol": result.symbol,
        "strategy_config_id": strategy_config_id,
        "num_windows": result.num_windows,
        "total_trades_across_windows": result.total_trades_across_windows,
        "aggregate_win_rate": result.aggregate_win_rate,
        "aggregate_profit_factor": result.aggregate_profit_factor,
        "worst_window_drawdown_pct": result.worst_window_drawdown_pct,
        "passed": result.passed,
        "min_trades_threshold": result.min_trades_threshold,
        "min_profit_factor_threshold": result.min_profit_factor_threshold,
    }

    response = db.table("walk_forward_results").insert(record).execute()

    # Update live_eligible ONLY if passed
    if result.passed and strategy_config_id:
        db.table("strategy_config").update({
            "live_eligible": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", strategy_config_id).execute()
        logger.info(f"✅ {result.symbol} is now live_eligible (walk-forward passed)")
    elif not result.passed:
        logger.info(f"❌ {result.symbol} did NOT pass walk-forward: {result.pass_reason}")

    return response.data[0] if response.data else record
