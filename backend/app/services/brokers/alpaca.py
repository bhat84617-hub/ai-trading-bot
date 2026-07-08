"""
Real Alpaca broker integration.

ccxt does NOT support Alpaca (it's crypto-exchange-only), so this talks to
Alpaca's own REST API directly: https://docs.alpaca.markets/reference

Paper trading uses https://paper-api.alpaca.markets
Live trading uses  https://api.alpaca.markets
Market data (quotes) uses https://data.alpaca.markets
"""
import httpx
from typing import Dict, List, Optional
from loguru import logger


class AlpacaBroker:
    def __init__(self, api_key: str, secret_key: str, is_paper: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.is_paper = is_paper
        self.base_url = "https://paper-api.alpaca.markets" if is_paper else "https://api.alpaca.markets"
        self.data_url = "https://data.alpaca.markets"

    def _headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
        }

    async def get_account(self) -> Optional[Dict]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self.base_url}/v2/account", headers=self._headers())
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Alpaca get_account failed: {e}")
            return None

    async def get_account_balance(self) -> float:
        acct = await self.get_account()
        if not acct:
            return 0.0
        try:
            return float(acct.get("cash", acct.get("equity", 0.0)))
        except (TypeError, ValueError):
            return 0.0

    async def place_order(self, symbol: str, side: str, order_type: str, qty: float,
                           price: Optional[float] = None, params: Optional[Dict] = None) -> Optional[Dict]:
        body = {
            "symbol": symbol.upper(),
            "qty": str(qty),
            "side": side,          # "buy" | "sell"
            "type": order_type,    # "market" | "limit" | "stop"
            "time_in_force": "day",
        }
        if order_type == "limit" and price:
            body["limit_price"] = str(price)
        if order_type == "stop" and price:
            body["stop_price"] = str(price)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{self.base_url}/v2/orders", headers=self._headers(), json=body)
                resp.raise_for_status()
                order = resp.json()
                logger.info(f"Alpaca order placed: {side} {qty} {symbol}")
                return {
                    "id": order.get("id", ""),
                    "symbol": order.get("symbol", symbol),
                    "side": order.get("side", side),
                    "amount": float(order.get("qty", qty)),
                    "price": price,
                    "status": order.get("status", "open"),
                    "filled": float(order.get("filled_qty", 0) or 0),
                    "remaining": qty - float(order.get("filled_qty", 0) or 0),
                    "timestamp": order.get("submitted_at"),
                }
        except httpx.HTTPStatusError as e:
            logger.error(f"Alpaca order failed [{e.response.status_code}]: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Alpaca order failed: {e}")
            return None

    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.delete(f"{self.base_url}/v2/orders/{order_id}", headers=self._headers())
                return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Alpaca cancel_order failed: {e}")
            return False

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        try:
            params = {"status": "open"}
            if symbol:
                params["symbols"] = symbol.upper()
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self.base_url}/v2/orders", headers=self._headers(), params=params)
                resp.raise_for_status()
                return [{
                    "id": o["id"], "symbol": o["symbol"], "side": o["side"],
                    "amount": float(o["qty"]), "price": o.get("limit_price"),
                    "status": o["status"], "timestamp": o.get("submitted_at"),
                } for o in resp.json()]
        except Exception as e:
            logger.error(f"Alpaca get_open_orders failed: {e}")
            return []

    async def get_positions(self) -> List[Dict]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self.base_url}/v2/positions", headers=self._headers())
                resp.raise_for_status()
                return [{
                    "symbol": p["symbol"], "side": "long" if float(p["qty"]) > 0 else "short",
                    "contracts": abs(float(p["qty"])), "entry_price": float(p["avg_entry_price"]),
                    "current_price": float(p["current_price"]), "pnl": float(p["unrealized_pl"]),
                    "percentage": float(p["unrealized_plpc"]) * 100,
                } for p in resp.json()]
        except Exception as e:
            logger.error(f"Alpaca get_positions failed: {e}")
            return []

    async def check_order_status(self, order_id: str, symbol: str = "") -> Optional[Dict]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self.base_url}/v2/orders/{order_id}", headers=self._headers())
                resp.raise_for_status()
                o = resp.json()
                return {
                    "id": o["id"], "status": o["status"],
                    "filled": float(o.get("filled_qty", 0) or 0),
                    "remaining": float(o["qty"]) - float(o.get("filled_qty", 0) or 0),
                    "price": o.get("filled_avg_price") or o.get("limit_price"),
                }
        except Exception as e:
            logger.error(f"Alpaca check_order_status failed: {e}")
            return None
