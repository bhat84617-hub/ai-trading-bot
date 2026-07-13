"""
EXECUTION ENGINE — Main scan cycle orchestrator.
==================================================
Fetches watchlist, generates signals, performs ALL risk checks,
and places orders through the broker adapter.

Pre-order checks (in this EXACT order):
1. Kill switch active? → Skip
2. Daily loss limit breached? → Auto-activate kill switch + skip
3. Max open positions reached? → Skip
4. Mode == live? → Check live_armed_until > now() AND live_eligible == true
5. Calculate position size (risk-based, NEVER flat)
6. Attach stop-loss to EVERY order (no naked entries, EVER)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta

from app.database import get_supabase
from app.brokers.interface import IBrokerAdapter, OrderRequest
from app.engine.signals import generate_signal, StrategyParams
from app.engine.risk import full_risk_check

logger = logging.getLogger(__name__)


def run_scan_cycle(broker: IBrokerAdapter) -> dict:
    """
    Execute one full scan cycle:
    1. Fetch active watchlist
    2. For each symbol: fetch bars → generate signal → risk check → execute
    3. Update account snapshots
    """
    start_time = time.time()
    db = get_supabase()

    # Get system state
    state_result = db.table("system_state").select("*").limit(1).execute()
    if not state_result.data:
        return {"error": "No system state found"}
    system_state = state_result.data[0]
    trading_mode = system_state.get("trading_mode", "paper")

    # Get active watchlist
    watchlist = (
        db.table("watchlist")
        .select("*")
        .eq("active", True)
        .execute()
    )
    symbols = watchlist.data or []

    signals_generated = []
    orders_placed = []
    errors = []

    # Get account info for risk calculations
    try:
        account = broker.get_account()
        equity = account.equity
    except Exception as e:
        logger.error(f"Failed to fetch account: {e}")
        return {"error": f"Failed to fetch account: {e}"}

    for item in symbols:
        symbol = item["symbol"]

        try:
            # Fetch strategy config
            config_result = (
                db.table("strategy_config")
                .select("*")
                .eq("symbol", symbol)
                .limit(1)
                .execute()
            )

            if config_result.data:
                cfg = config_result.data[0]
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
            else:
                params = StrategyParams()

            # Fetch OHLCV bars (minimum timeframe: 5 minutes)
            end_time = datetime.now(timezone.utc)
            start_time_data = end_time - timedelta(days=30)

            bars_df = broker.get_bars(
                symbol=symbol,
                timeframe="5Min",
                start=start_time_data,
                end=end_time,
                limit=1000,
            )

            if bars_df is None or len(bars_df) < 60:
                logger.warning(f"Insufficient data for {symbol}: {len(bars_df) if bars_df is not None else 0} bars")
                continue

            # Generate signal using SHARED engine
            signal = generate_signal(bars_df, symbol, params)
            signals_generated.append({
                "symbol": symbol,
                "direction": signal.direction,
                "regime": signal.regime,
                "confirming_indicators": signal.confirming_indicators,
                "confidence": signal.confidence,
            })

            if signal.direction == "hold" or signal.confidence < 2:
                continue

            # Get current price
            try:
                quote = broker.get_quote(symbol)
                entry_price = quote.last if quote.last > 0 else bars_df.iloc[-1]["close"]
            except Exception:
                entry_price = bars_df.iloc[-1]["close"]

            # FULL RISK CHECK — all mandatory gates
            risk_result = full_risk_check(
                symbol=symbol,
                side=signal.direction,
                entry_price=entry_price,
                atr=signal.atr,
                equity=equity,
                trading_mode=trading_mode,
            )

            if not risk_result.allowed:
                logger.info(
                    f"Trade blocked for {symbol}: {risk_result.reason}"
                )
                continue

            # Place order with MANDATORY stop-loss
            order = OrderRequest(
                symbol=symbol,
                side=signal.direction,
                qty=risk_result.position_size,
                order_type="market",
                stop_loss=risk_result.stop_loss_price,
                take_profit=risk_result.take_profit_price,
            )

            result = broker.place_order(order)

            # Log to trade_history
            trade_record = {
                "symbol": symbol,
                "side": signal.direction,
                "entry_price": entry_price,
                "quantity": risk_result.position_size,
                "stop_loss": risk_result.stop_loss_price,
                "take_profit": risk_result.take_profit_price,
                "status": "open" if result.status in ("filled", "pending") else "failed",
                "signal_reason": {
                    "regime": signal.regime,
                    "confirming_indicators": signal.confirming_indicators,
                    "confidence": signal.confidence,
                    "indicator_values": signal.indicator_values,
                },
                "broker": "alpaca",
                "mode": trading_mode,
            }
            db.table("trade_history").insert(trade_record).execute()

            orders_placed.append({
                "symbol": symbol,
                "side": signal.direction,
                "qty": risk_result.position_size,
                "status": result.status,
                "order_id": result.order_id,
            })

            logger.info(
                f"Order placed: {signal.direction} {risk_result.position_size} "
                f"{symbol} @ ~{entry_price} | SL: {risk_result.stop_loss_price} | "
                f"TP: {risk_result.take_profit_price} | Mode: {trading_mode}"
            )

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            errors.append({"symbol": symbol, "error": str(e)})

    # Update account snapshot
    try:
        account = broker.get_account()
        db.table("account_snapshots").insert({
            "equity": account.equity,
            "buying_power": account.buying_power,
            "daily_pnl": account.daily_pnl,
        }).execute()
    except Exception as e:
        logger.error(f"Failed to snapshot account: {e}")

    elapsed = time.time() - start_time if isinstance(start_time, float) else 0

    return {
        "scanned_symbols": len(symbols),
        "signals": signals_generated,
        "orders_placed": orders_placed,
        "errors": errors,
        "scan_time_ms": round(elapsed * 1000, 2),
        "trading_mode": trading_mode,
    }
