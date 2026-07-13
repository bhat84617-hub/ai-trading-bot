"""
Backtest & Walk-Forward API router.
POST /api/backtest
POST /api/walk-forward
GET/PUT /api/strategy-config/{symbol}
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException

from app.database import get_supabase
from app.brokers.alpaca import AlpacaAdapter
from app.engine.signals import StrategyParams
from app.engine.backtest import run_backtest, save_backtest_result
from app.engine.walk_forward import run_walk_forward, save_walk_forward_result
from app.models.schemas import (
    BacktestRequest,
    BacktestResult,
    WalkForwardRequest,
    WalkForwardResult,
    StrategyConfig,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["backtest"])


def _get_alpaca_adapter():
    """Get Alpaca adapter helper."""
    try:
        return AlpacaAdapter()
    except Exception as e:
        logger.error(f"Failed to initialize Alpaca adapter: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize Alpaca adapter. Check API keys. Error: {e}"
        )


@router.get("/api/strategy-config/{symbol}", response_model=StrategyConfig)
async def get_strategy_config(symbol: str):
    """Retrieve strategy config for a symbol."""
    db = get_supabase()
    result = (
        db.table("strategy_config")
        .select("*")
        .eq("symbol", symbol.upper())
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Strategy config not found for {symbol}")
    return result.data[0]


@router.put("/api/strategy-config/{symbol}", response_model=StrategyConfig)
async def update_strategy_config(symbol: str, config: StrategyConfig):
    """Update strategy config parameters for a symbol. Resets live_eligible to false if parameters change."""
    db = get_supabase()
    existing = (
        db.table("strategy_config")
        .select("*")
        .eq("symbol", symbol.upper())
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail=f"Strategy config not found for {symbol}")
        
    cfg_id = existing.data[0]["id"]
    
    # Check if critical parameters changed (reset validation eligibility)
    reset_eligible = False
    old = existing.data[0]
    
    if (
        old.get("rsi_period") != config.rsi_period or
        old.get("rsi_overbought") != config.rsi_overbought or
        old.get("rsi_oversold") != config.rsi_oversold or
        old.get("macd_fast") != config.macd_fast or
        old.get("macd_slow") != config.macd_slow or
        old.get("macd_signal") != config.macd_signal or
        old.get("ma_short") != config.ma_short or
        old.get("ma_long") != config.ma_long
    ):
        reset_eligible = True
        logger.info(f"Strategy parameters changed for {symbol}. Resetting live_eligible to false.")

    update_data = {
        "rsi_period": config.rsi_period,
        "rsi_overbought": config.rsi_overbought,
        "rsi_oversold": config.rsi_oversold,
        "macd_fast": config.macd_fast,
        "macd_slow": config.macd_slow,
        "macd_signal": config.macd_signal,
        "ma_short": config.ma_short,
        "ma_long": config.ma_long,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    if reset_eligible:
        update_data["live_eligible"] = False
    else:
        update_data["live_eligible"] = config.live_eligible

    result = db.table("strategy_config").update(update_data).eq("id", cfg_id).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to update strategy config")
        
    return result.data[0]


@router.post("/api/backtest", response_model=BacktestResult)
async def run_backtest_endpoint(req: BacktestRequest):
    """
    Run backtest on demand.
    Loads historical data, runs the shared engine backtest, and saves to database.
    """
    db = get_supabase()
    alpaca = _get_alpaca_adapter()

    # Get strategy config row for the symbol to associate with results
    config_result = (
        db.table("strategy_config")
        .select("id")
        .eq("symbol", req.symbol.upper())
        .limit(1)
        .execute()
    )
    strategy_config_id = config_result.data[0]["id"] if config_result.data else None

    # Fetch bars
    start_dt = datetime.combine(req.period_start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(req.period_end, datetime.max.time(), tzinfo=timezone.utc)
    
    try:
        df = alpaca.get_bars(
            symbol=req.symbol.upper(),
            timeframe="5Min",
            start=start_dt,
            end=end_dt,
            limit=10000,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch market data: {e}")

    if df is None or len(df) < 50:
        raise HTTPException(status_code=400, detail=f"Not enough data bars returned ({len(df) if df is not None else 0}) for backtesting.")

    params = StrategyParams(
        rsi_period=req.rsi_period,
        rsi_overbought=req.rsi_overbought,
        rsi_oversold=req.rsi_oversold,
        macd_fast=req.macd_fast,
        macd_slow=req.macd_slow,
        macd_signal=req.macd_signal,
        ma_short=req.ma_short,
        ma_long=req.ma_long,
    )

    # Run backtest using shared engine code
    output = run_backtest(
        df=df,
        symbol=req.symbol.upper(),
        params=params,
    )

    # Save to db
    db_record = save_backtest_result(output, strategy_config_id)
    
    # Return formatted backtest result
    return BacktestResult(
        id=db_record.get("id"),
        symbol=output.symbol,
        strategy_config_id=strategy_config_id,
        period_start=req.period_start,
        period_end=req.period_end,
        total_trades=output.total_trades,
        win_rate=output.win_rate,
        avg_r_multiple=output.avg_r_multiple,
        profit_factor=output.profit_factor,
        max_drawdown_pct=output.max_drawdown_pct,
        created_at=datetime.now(timezone.utc),
    )


@router.post("/api/walk-forward", response_model=WalkForwardResult)
async def run_walk_forward_endpoint(req: WalkForwardRequest):
    """
    Run walk-forward validation on demand.
    If validation passes, updates live_eligible to true for the symbol config.
    """
    db = get_supabase()
    alpaca = _get_alpaca_adapter()

    # Get strategy config
    config_result = (
        db.table("strategy_config")
        .select("*")
        .eq("symbol", req.symbol.upper())
        .limit(1)
        .execute()
    )
    if not config_result.data:
        raise HTTPException(status_code=404, detail=f"Strategy config not found for {req.symbol}")
    
    cfg = config_result.data[0]
    strategy_config_id = cfg["id"]

    params = StrategyParams(
        rsi_period=cfg.get("rsi_period", 14),
        rsi_overbought=cfg.get("rsi_overbought", 70),
        rsi_oversold=cfg.get("rsi_oversold", 30),
        macd_fast=cfg.get("macd_fast", 12),
        macd_slow=cfg.get("macd_slow", 26),
        macd_signal=cfg.get("macd_signal", 9),
        ma_short=cfg.get("ma_short", 20),
        ma_long=cfg.get("ma_long", 50),
    )

    # Fetch bars
    start_dt = datetime.combine(req.period_start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(req.period_end, datetime.max.time(), tzinfo=timezone.utc)

    try:
        df = alpaca.get_bars(
            symbol=req.symbol.upper(),
            timeframe="5Min",
            start=start_dt,
            end=end_dt,
            limit=15000,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch market data: {e}")

    if df is None or len(df) < 200:
        raise HTTPException(status_code=400, detail=f"Not enough historical data ({len(df) if df is not None else 0} bars) for walk-forward validation.")

    # Run Walk-Forward validation
    output = run_walk_forward(
        df=df,
        symbol=req.symbol.upper(),
        num_windows=req.num_windows,
        params=params,
        min_trades_threshold=req.min_trades_threshold,
        min_profit_factor_threshold=req.min_profit_factor_threshold,
    )

    # Save to db + update live_eligible
    db_record = save_walk_forward_result(output, strategy_config_id)

    return WalkForwardResult(
        id=db_record.get("id"),
        symbol=output.symbol,
        strategy_config_id=strategy_config_id,
        num_windows=output.num_windows,
        total_trades_across_windows=output.total_trades_across_windows,
        aggregate_win_rate=output.aggregate_win_rate,
        aggregate_profit_factor=output.aggregate_profit_factor,
        worst_window_drawdown_pct=output.worst_window_drawdown_pct,
        passed=output.passed,
        min_trades_threshold=output.min_trades_threshold,
        min_profit_factor_threshold=output.min_profit_factor_threshold,
        created_at=datetime.now(timezone.utc),
    )
