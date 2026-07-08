import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from loguru import logger
from ..core.redis_client import redis_client
from ..core.config import settings
import asyncio
import json
import yfinance as yf

FOREX_PAIRS = {'EUR/USD','GBP/USD','USD/JPY','GBP/JPY','AUD/USD','USD/CAD','NZD/USD','USD/CHF','EUR/JPY','EUR/GBP'}

# Bug fix: the original code called `ccxt.alpaca(...)` and `ccxt.oanda(...)`.
# ccxt is a CRYPTO-ONLY exchange library — it has never had Alpaca, OANDA, or
# Tradier classes, at any version. Every call for a stock symbol (TSLA, AAPL,
# MSFT, ...) or forex pair was crashing with AttributeError and getting
# silently swallowed by the except block below, returning empty data. That's
# why nothing but (sometimes) crypto ever showed up.
#
# Fix: use yfinance for stocks and forex (no API key needed, works out of the
# box), and keep ccxt strictly for real crypto exchanges (binance etc).
_TF_TO_YF_INTERVAL = {
    '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
    '1h': '60m', '4h': '60m', '1d': '1d', '1w': '1wk',
}

class MarketDataService:
    def __init__(self):
        self.exchanges = {}
        self.supported_timeframes = {
            '1m': 60, '5m': 300, '15m': 900, '30m': 1800,
            '1h': 3600, '4h': 14400, '1d': 86400, '1w': 604800
        }

    def _asset_class(self, symbol: str) -> str:
        sym_upper = symbol.upper()
        if '/' in sym_upper:
            if sym_upper in FOREX_PAIRS or not sym_upper.endswith(('USD', 'USDT')):
                return 'forex'
            return 'crypto'
        return 'stock'

    async def _get_crypto_exchange(self):
        if 'binance' not in self.exchanges:
            self.exchanges['binance'] = ccxt.binance({'enableRateLimit': True})
        return self.exchanges['binance']

    async def _fetch_ohlcv_yfinance(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        # yfinance is sync — run it off the event loop so it doesn't block other scans.
        yf_symbol = symbol.replace('/', '') + '=X' if self._asset_class(symbol) == 'forex' else symbol
        interval = _TF_TO_YF_INTERVAL.get(timeframe, '60m')
        period_map = {
            '1m': '7d', '5m': '60d', '15m': '60d', '30m': '60d',
            '60m': '730d', '1d': '2y', '1wk': '5y',
        }
        period = period_map.get(interval, '1y')

        def _download():
            data = yf.Ticker(yf_symbol).history(period=period, interval=interval)
            return data

        loop = asyncio.get_event_loop()
        hist = await loop.run_in_executor(None, _download)
        if hist is None or hist.empty:
            return pd.DataFrame()

        hist = hist.tail(limit).reset_index()
        time_col = 'Datetime' if 'Datetime' in hist.columns else 'Date'
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(hist[time_col]),
            'open': hist['Open'], 'high': hist['High'],
            'low': hist['Low'], 'close': hist['Close'],
            'volume': hist['Volume'],
        })
        df.set_index('timestamp', inplace=True)
        return df

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 200) -> pd.DataFrame:
        cache_key = f"ohlcv:{symbol}:{timeframe}:{limit}"
        cached = await redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            return df

        asset_class = self._asset_class(symbol)
        try:
            if asset_class == 'crypto':
                exchange = await self._get_crypto_exchange()
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
            else:
                df = await self._fetch_ohlcv_yfinance(symbol, timeframe, limit)

            if df.empty:
                return df
            cache_data = df.reset_index().to_dict('records')
            await redis_client.set(cache_key, cache_data, ttl=60)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch {symbol} {timeframe} ({asset_class}): {e}")
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
            asset_class = self._asset_class(symbol)
            if asset_class == 'crypto':
                exchange = await self._get_crypto_exchange()
                ticker = await exchange.fetch_ticker(symbol)
                price = ticker['last']
            else:
                yf_symbol = symbol.replace('/', '') + '=X' if asset_class == 'forex' else symbol

                def _fetch():
                    t = yf.Ticker(yf_symbol)
                    fast = t.fast_info
                    return fast.get('lastPrice') or fast.get('last_price')

                loop = asyncio.get_event_loop()
                price = await loop.run_in_executor(None, _fetch)
                if price is None:
                    return None
            await redis_client.set(cache_key, price, ttl=10)
            return price
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    async def get_order_book(self, symbol: str, limit: int = 50) -> Optional[Dict]:
        # Order books only exist for crypto exchanges here (yfinance has no
        # order book data for stocks/forex).
        if self._asset_class(symbol) != 'crypto':
            logger.warning(f"Order book not available for non-crypto symbol {symbol}")
            return None
        try:
            exchange = await self._get_crypto_exchange()
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
