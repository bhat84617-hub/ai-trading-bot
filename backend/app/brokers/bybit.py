"""
Bybit broker adapter — P2 stub for crypto trading.
Not implemented in this version. Will be built after step 13 is stable.
"""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from app.brokers.interface import (
    IBrokerAdapter,
    Quote,
    AccountInfo,
    Position,
    OrderRequest,
    OrderResult,
)

logger = logging.getLogger(__name__)


class BybitAdapter(IBrokerAdapter):
    """
    Bybit crypto adapter — P2 stub.
    All methods raise NotImplementedError until Phase 14.
    """

    def get_quote(self, symbol: str) -> Quote:
        raise NotImplementedError("Bybit adapter is not yet implemented (P2)")

    def get_account(self) -> AccountInfo:
        raise NotImplementedError("Bybit adapter is not yet implemented (P2)")

    def get_positions(self) -> list[Position]:
        raise NotImplementedError("Bybit adapter is not yet implemented (P2)")

    def place_order(self, order: OrderRequest) -> OrderResult:
        raise NotImplementedError("Bybit adapter is not yet implemented (P2)")

    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError("Bybit adapter is not yet implemented (P2)")

    def get_bars(
        self,
        symbol: str,
        timeframe: str = "5Min",
        start: datetime = None,
        end: datetime = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        raise NotImplementedError("Bybit adapter is not yet implemented (P2)")
