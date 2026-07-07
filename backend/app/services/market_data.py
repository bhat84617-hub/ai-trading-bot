import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from loguru import logger
from ..core.redis_client import redis_client
from ..core.config import settings
import asyncio
import json

FOREX_PAIRS = {'EUR/USD','GBP/USD','USD/JPY','GBP/JPY','AUD/USD','USD/CAD','NZD/USD','USD/CHF','EUR/JPY','EUR/GBP'}

class MarketDataService:
    def __init__(self):
        self.exchanges = {}
        self.supported_timeframes = {
            '1m': 60, '5m': 300, '15m': 900, '30m': 1800,
            '1h': 3600, '4h': 14400, '1d': 86400, '1w': 604800
        }

    async def _get_exchange(self, symbol: str):
        sym_upper = symbol.upper()
        if sym_upper in FOREX_PAIRS or ('/' in sym_upper and not sym_upper.endswith('USD')):
            exchange_id = 'oanda'
        elif '/' in sym_upper:
            exchange_id = 'binance'
        else:
            exchange_id = 'alpaca'

        if exchange_id not in self.exchanges:
            if exchange_id == 'binance':
                self.exchanges[exchange_id] = ccxt.binance({'enableRateLimit': True})
            elif exchange_id == 'oanda':
                self.exchanges[exchange_id] = ccxt.oanda({
                    'apiKey': settings.BROKER_API_KEY or 'demo',
                    'secret': settings.BROKER_SECRET_KEY or 'demo',
                    'enableRateLimit': True,
                })
            else:
                self.exchanges[exchange_id] = ccxt.alpaca({
                    'apiKey': settings.BROKER_PAPER_KEY,
                    'secret': settings.BROKER_PAPER_SECRET,
                    'enableRateLimit': True,
                })
        return self.exchanges[exchange_id]

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> pd.DataFrame:
        cache_key = f"ohlcv:{symbol}:{timeframe}:{limit}"
        cached = await redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df

        try:
            exchange = await self._get_exchange(symbol)
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            cache_data = df.reset_index().to_dict('records')
            await redis_client.set(cache_key, cache_data, ttl=60)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch {symbol} {timeframe}: {e}")
            return pd.DataFrame()

    async def fetch_multiple_timeframes(self, symbol: str, timeframes: List[str] = None, limit: int = 200) -> Dict[str, pd.DataFrame]:
        if timeframes is None:
            timeframes = ['5m', '15m', '1h', '4h', '1d']
        tasks = {tf: self.fetch_ohlcv(symbol, tf, limit) for tf in timeframes}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return {tf: res for tf, res in zip(timeframes, results) if isinstance(res, pd.DataFrame) and not res.empty}

    async def get_current_price(self, symbol: str) -> Optional[float]:
        cache_key = f"price:{symbol}"
        cached = await redis_client.get(cache_key)
        if cached:
            return float(cached)
        try:
            exchange = await self._get_exchange(symbol)
            ticker = await exchange.fetch_ticker(symbol)
            price = ticker['last']
            await redis_client.set(cache_key, price, ttl=10)
            return price
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    async def get_order_book(self, symbol: str, limit: int = 50) -> Optional[Dict]:
        try:
            exchange = await self._get_exchange(symbol)
            orderbook = await exchange.fetch_order_book(symbol, limit)
            return {
                'bids': orderbook['bids'][:10],
                'asks': orderbook['asks'][:10],
                'spread': orderbook['asks'][0][0] - orderbook['bids'][0][0],
                'mid_price': (orderbook['asks'][0][0] + orderbook['bids'][0][0]) / 2
            }
        except Exception as e:
            logger.error(f"Failed to fetch order book for {symbol}: {e}")
            return None

market_data_service = MarketDataService()
