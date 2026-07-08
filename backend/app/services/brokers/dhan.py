"""
Dhan Trading API (India) — Custom connector
Docs: https://dhanhq.co/docs/v2/
"""
import httpx
from typing import Dict, Optional, List
from loguru import logger


class DhanBroker:
    def __init__(self, client_id: str, access_token: str, is_paper: bool = True):
        self.client_id = client_id
        self.access_token = access_token
        self.base_url = "https://api.dhanhq.co/v2" if not is_paper else "https://api.dhanhq.co/v2"  # Dhan has sandbox via separate token
        self.is_paper = is_paper
        self._headers = {
            "access-token": access_token,
            "client-id": client_id,
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(method, f"{self.base_url}{path}", headers=self._headers, json=data)
            if resp.status_code == 429:
                logger.warning("Dhan rate limited, retrying...")
                import asyncio
                await asyncio.sleep(2)
                resp = await client.request(method, f"{self.base_url}{path}", headers=self._headers, json=data)
            resp.raise_for_status()
            return resp.json()

    async def get_account_balance(self) -> float:
        try:
            data = await self._request("GET", "/funds")
            return float(data.get("balance", {}).get("availableBalance", 0))
        except Exception as e:
            logger.error(f"Dhan balance error: {e}")
            return 0

    async def get_positions(self) -> List[Dict]:
        try:
            data = await self._request("GET", "/positions")
            return data.get("positions", [])
        except:
            return []

    async def place_order(self, symbol: str, side: str, quantity: float, order_type: str = "MARKET",
                          price: Optional[float] = None) -> Optional[Dict]:
        try:
            payload = {
                "dhanClientId": self.client_id,
                "transactionType": side.upper(),  # BUY or SELL
                "exchange": "NSE" if "NSE" in symbol else "BSE",
                "securityId": symbol.split(":")[-1] if ":" in symbol else symbol,
                "orderType": order_type.upper() if order_type else "MARKET",
                "quantity": int(quantity),
                "price": price or 0,
                "productType": "CNC" if not self.is_paper else "INTRADAY",
            }
            return await self._request("POST", "/orders", payload)
        except Exception as e:
            logger.error(f"Dhan order error: {e}")
            return None

    async def get_order_status(self, order_id: str) -> Optional[Dict]:
        try:
            return await self._request("GET", f"/orders/{order_id}")
        except:
            return None
