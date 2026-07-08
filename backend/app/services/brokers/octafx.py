"""
OctaFX Trading API — Custom connector
OctaFX uses MT4/MT5 bridge via REST API
Docs: https://octafx.com/api-docs
"""
import httpx
from typing import Dict, Optional, List
from loguru import logger


class OctaFXBroker:
    def __init__(self, api_key: str, account_id: str, is_paper: bool = True):
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = "https://api.octafx.com/v1" if not is_paper else "https://demo-api.octafx.com/v1"
        self.is_paper = is_paper
        self._headers = {
            "X-API-Key": api_key,
            "X-Account-Id": account_id,
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.request(method, f"{self.base_url}{path}", headers=self._headers, json=data)
            resp.raise_for_status()
            return resp.json()

    async def get_account_balance(self) -> float:
        try:
            data = await self._request("GET", "/account")
            return float(data.get("balance", 0))
        except Exception as e:
            logger.error(f"OctaFX balance error: {e}")
            return 0

    async def get_positions(self) -> List[Dict]:
        try:
            data = await self._request("GET", "/positions")
            return data.get("positions", [])
        except:
            return []

    async def place_order(self, symbol: str, side: str, volume: float, order_type: str = "market",
                          price: Optional[float] = None, sl: Optional[float] = None,
                          tp: Optional[float] = None) -> Optional[Dict]:
        try:
            payload = {
                "symbol": symbol,
                "side": side.upper(),
                "volume": volume,
                "type": order_type.upper(),
                "price": price or 0,
            }
            if sl:
                payload["stopLoss"] = sl
            if tp:
                payload["takeProfit"] = tp
            return await self._request("POST", "/orders", payload)
        except Exception as e:
            logger.error(f"OctaFX order error: {e}")
            return None

    async def close_position(self, position_id: str) -> bool:
        try:
            await self._request("DELETE", f"/positions/{position_id}")
            return True
        except:
            return False
