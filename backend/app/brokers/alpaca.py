"""
Alpaca broker adapter — supports US stocks (paper + live).
Uses alpaca-py SDK for trading and market data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from app.brokers.interface import (
    IBrokerAdapter,
    Quote,
    AccountInfo,
    Position,
    OrderRequest,
    OrderResult,
)
from app.config import get_settings

logger = logging.getLogger(__name__)


class AlpacaAdapter(IBrokerAdapter):
    """Concrete Alpaca broker adapter for US stocks."""

    def __init__(self):
        settings = get_settings()
        is_paper = "paper" in settings.alpaca_base_url.lower()

        self.trading_client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=is_paper,
        )
        self.data_client = StockHistoricalDataClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
        )

    def get_quote(self, symbol: str) -> Quote:
        """Fetch latest quote via Alpaca data API."""
        try:
            snapshot = self.data_client.get_stock_latest_quote(
                request_params={"symbol_or_symbols": symbol}
            )
            q = snapshot[symbol]
            return Quote(
                symbol=symbol,
                bid=float(q.bid_price) if q.bid_price else 0.0,
                ask=float(q.ask_price) if q.ask_price else 0.0,
                last=float(q.ask_price) if q.ask_price else 0.0,
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"Alpaca get_quote error for {symbol}: {e}")
            raise

    def get_account(self) -> AccountInfo:
        """Fetch account info from Alpaca."""
        try:
            acct = self.trading_client.get_account()
            return AccountInfo(
                equity=float(acct.equity),
                buying_power=float(acct.buying_power),
                cash=float(acct.cash),
                daily_pnl=float(acct.equity) - float(acct.last_equity),
            )
        except Exception as e:
            logger.error(f"Alpaca get_account error: {e}")
            raise

    def get_positions(self) -> list[Position]:
        """Fetch all open positions from Alpaca."""
        try:
            positions = self.trading_client.get_all_positions()
            result = []
            for p in positions:
                result.append(
                    Position(
                        symbol=p.symbol,
                        qty=float(p.qty),
                        avg_entry_price=float(p.avg_entry_price),
                        current_price=float(p.current_price),
                        unrealized_pnl=float(p.unrealized_pl),
                        market_value=float(p.market_value),
                        side="long" if float(p.qty) > 0 else "short",
                    )
                )
            return result
        except Exception as e:
            logger.error(f"Alpaca get_positions error: {e}")
            raise

    def place_order(self, order: OrderRequest) -> OrderResult:
        """
        Place an order on Alpaca.
        Stop-loss MUST be provided — enforced by the risk engine before calling this.
        """
        if order.stop_loss is None:
            raise ValueError("CRITICAL: Cannot place order without stop-loss. This is a mandatory safety gate.")

        try:
            side = OrderSide.BUY if order.side == "buy" else OrderSide.SELL

            # Build bracket order (entry + stop-loss + optional take-profit)
            stop_loss = StopLossRequest(stop_price=round(order.stop_loss, 2))
            take_profit = (
                TakeProfitRequest(limit_price=round(order.take_profit, 2))
                if order.take_profit
                else None
            )

            if order.order_type == "limit" and order.limit_price:
                request = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=side,
                    time_in_force=TimeInForce.GTC,
                    limit_price=round(order.limit_price, 2),
                    order_class=OrderClass.BRACKET,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
            else:
                request = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=side,
                    time_in_force=TimeInForce.GTC,
                    order_class=OrderClass.BRACKET,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )

            result = self.trading_client.submit_order(request)

            return OrderResult(
                order_id=str(result.id),
                symbol=result.symbol,
                side=order.side,
                qty=float(result.qty),
                status=str(result.status.value) if result.status else "pending",
                filled_price=float(result.filled_avg_price) if result.filled_avg_price else None,
                message=f"Order placed: {result.id}",
            )
        except Exception as e:
            logger.error(f"Alpaca place_order error: {e}")
            return OrderResult(
                order_id="",
                symbol=order.symbol,
                side=order.side,
                qty=order.qty,
                status="failed",
                message=str(e),
            )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order on Alpaca."""
        try:
            self.trading_client.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.error(f"Alpaca cancel_order error for {order_id}: {e}")
            return False

    def get_bars(
        self,
        symbol: str,
        timeframe: str = "5Min",
        start: datetime = None,
        end: datetime = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV bars from Alpaca.
        Returns DataFrame with columns: open, high, low, close, volume.
        """
        try:
            # Parse timeframe string
            tf_map = {
                "1Min": TimeFrame(1, TimeFrameUnit.Minute),
                "5Min": TimeFrame(5, TimeFrameUnit.Minute),
                "15Min": TimeFrame(15, TimeFrameUnit.Minute),
                "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
                "1Day": TimeFrame(1, TimeFrameUnit.Day),
            }
            tf = tf_map.get(timeframe, TimeFrame(5, TimeFrameUnit.Minute))

            request_params = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start,
                end=end,
                limit=limit,
            )

            bars = self.data_client.get_stock_bars(request_params)
            df = bars.df

            if isinstance(df.index, pd.MultiIndex):
                df = df.droplevel("symbol")

            df = df.rename(
                columns={
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                }
            )
            return df[["open", "high", "low", "close", "volume"]]

        except Exception as e:
            logger.error(f"Alpaca get_bars error for {symbol}: {e}")
            raise
