"""
Broker adapter abstract interface.
Two concrete adapters only: Alpaca (stocks) and Bybit (crypto, P2).
No generic plugin system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd


@dataclass
class Quote:
    symbol: str
    bid: float
    ask: float
    last: float
    timestamp: datetime


@dataclass
class AccountInfo:
    equity: float
    buying_power: float
    cash: float
    daily_pnl: float


@dataclass
class Position:
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    market_value: float
    side: str  # 'long' or 'short'


@dataclass
class OrderRequest:
    symbol: str
    side: str  # 'buy' or 'sell'
    qty: float
    order_type: str = "market"  # 'market' or 'limit'
    limit_price: Optional[float] = None
    stop_loss: Optional[float] = None     # MANDATORY — enforced by risk engine
    take_profit: Optional[float] = None
    time_in_force: str = "gtc"


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: str
    qty: float
    status: str  # 'filled', 'pending', 'rejected', 'cancelled'
    filled_price: Optional[float] = None
    message: str = ""


class IBrokerAdapter(ABC):
    """
    Abstract broker adapter interface.
    Only two implementations: AlpacaAdapter and BybitAdapter.
    """

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        """Fetch current quote for a symbol."""
        ...

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """Fetch account equity, buying power, cash, daily P&L."""
        ...

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Fetch all open positions."""
        ...

    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResult:
        """
        Place an order with the broker.
        The order MUST have a stop_loss attached — the risk engine
        enforces this before calling place_order.
        """
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order. Returns True if successfully cancelled."""
        ...

    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV bars.
        Returns a DataFrame with columns: open, high, low, close, volume
        indexed by timestamp.
        """
        ...
