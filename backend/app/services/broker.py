import ccxt.async_support as ccxt
from typing import Dict, Optional, List, Tuple
from loguru import logger
from ..core.config import settings
from ..core.redis_client import redis_client
from .market_data import market_data_service

_EXCHANGE_IDS = {
    'binance': 'binance', 'bybit': 'bybit', 'okx': 'okx',
    'kucoin': 'kucoin', 'kraken': 'kraken', 'coinbase': 'coinbase',
    'gateio': 'gate',   # gateio ka CCXT naam `gate` hai
    'gate': 'gate',
    'bitget': 'bitget', 'mexc': 'mexc', 'huobi': 'huobi',
    'bitfinex': 'bitfinex', 'cryptocom': 'cryptocom',
    'gemini': 'gemini', 'bitmart': 'bitmart', 'lbank': 'lbank',
    'poloniex': 'poloniex', 'ascendex': 'ascendex',
    'coindcx': 'coindcx',
    'alpaca': 'alpaca', 'tradier': 'tradier',
    'oanda': 'oanda',
}

SUPPORTED_EXCHANGES = {}
for name, ccxt_name in _EXCHANGE_IDS.items():
    try:
        cls = getattr(ccxt, ccxt_name)
        SUPPORTED_EXCHANGES[name] = cls
    except AttributeError:
        pass

SUPPORTED_EXCHANGES['dhan'] = 'custom_dhan'
SUPPORTED_EXCHANGES['octafx'] = 'custom_octafx'


class BrokerService:
    def __init__(self):
        self.is_live = settings.TRADE_MODE == "live"
        self.exchange = None
        self._broker_name = settings.BROKER_NAME

    async def switch_broker(self, broker_name: str):
        self._broker_name = broker_name.lower()
        self.exchange = None
        logger.info(f"Switched broker to {broker_name}")

    async def _get_exchange(self, broker_name: str = None):
        name = (broker_name or self._broker_name).lower()
        entry = SUPPORTED_EXCHANGES.get(name)

        if entry and isinstance(entry, str) and entry.startswith('custom_'):
            from .brokers import DhanBroker, OctaFXBroker
            if entry == 'custom_dhan':
                return DhanBroker(client_id=settings.BROKER_API_KEY or "dhan_client_id", access_token=settings.BROKER_SECRET_KEY or "dhan_token", is_paper=not self.is_live)
            elif entry == 'custom_octafx':
                return OctaFXBroker(api_key=settings.BROKER_API_KEY or "octafx_key", account_id=settings.BROKER_SECRET_KEY or "octafx_account", is_paper=not self.is_live)

        exchange_class = entry if entry else ccxt.binance

        if self.is_live:
            self.exchange = exchange_class({'apiKey': settings.BROKER_API_KEY, 'secret': settings.BROKER_SECRET_KEY, 'enableRateLimit': True})
        else:
            kwargs = {'apiKey': settings.BROKER_PAPER_KEY, 'secret': settings.BROKER_PAPER_SECRET, 'enableRateLimit': True}
            if hasattr(exchange_class, 'sandbox'):
                kwargs['sandbox'] = True
            self.exchange = exchange_class(kwargs)
        return self.exchange

    async def get_account_balance(self) -> float:
        try:
            exchange = await self._get_exchange()
            balance = await exchange.fetch_balance()
            if 'USD' in balance.get('total', {}):
                return float(balance['total']['USD'])
            if 'USDT' in balance.get('total', {}):
                return float(balance['total']['USDT'])
            total_usd = 0
            for currency, amount in balance.get('total', {}).items():
                if amount > 0 and currency != 'USD':
                    try:
                        ticker = await exchange.fetch_ticker(f"{currency}/USD")
                        total_usd += float(amount) * ticker['last']
                    except:
                        total_usd += float(amount)
                elif currency == 'USD':
                    total_usd += float(amount)
            return total_usd
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 100000.0

    async def place_order(self, symbol: str, side: str, order_type: str, amount: float, price: Optional[float] = None, params: Optional[Dict] = None) -> Optional[Dict]:
        try:
            exchange = await self._get_exchange()
            if params is None:
                params = {}
            order = await exchange.create_order(symbol, order_type, side, amount, price, params)
            logger.info(f"Order placed: {side} {amount} {symbol} @ {price}")
            return {'id': order.get('id', ''), 'symbol': order.get('symbol', symbol), 'side': order.get('side', side), 'amount': order.get('amount', amount), 'price': order.get('price', price), 'status': order.get('status', 'open'), 'filled': order.get('filled', 0), 'remaining': order.get('remaining', amount), 'timestamp': order.get('timestamp')}
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return None

    async def place_market_order(self, symbol: str, side: str, amount: float) -> Optional[Dict]:
        return await self.place_order(symbol, side, 'market', amount)

    async def place_limit_order(self, symbol: str, side: str, amount: float, price: float) -> Optional[Dict]:
        return await self.place_order(symbol, side, 'limit', amount, price)

    async def place_stop_loss_order(self, symbol: str, side: str, amount: float, stop_price: float) -> Optional[Dict]:
        return await self.place_order(symbol, side, 'stop', amount, stop_price, {'stopPrice': stop_price})

    async def place_take_profit_order(self, symbol: str, side: str, amount: float, price: float) -> Optional[Dict]:
        return await self.place_order(symbol, side, 'limit', amount, price)

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            exchange = await self._get_exchange()
            await exchange.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        try:
            exchange = await self._get_exchange()
            orders = await exchange.fetch_open_orders(symbol)
            return [{'id': o['id'], 'symbol': o['symbol'], 'side': o['side'], 'amount': o['amount'], 'price': o['price'], 'status': o['status'], 'timestamp': o['timestamp']} for o in orders]
        except Exception as e:
            logger.error(f"Failed to fetch open orders: {e}")
            return []

    async def get_positions(self) -> List[Dict]:
        try:
            exchange = await self._get_exchange()
            positions = await exchange.fetch_positions()
            return [{'symbol': p['symbol'], 'side': 'long' if p['side'] == 'long' else 'short', 'contracts': p['contracts'], 'entry_price': p['entryPrice'], 'current_price': p['currentPrice'], 'pnl': p['pnl'], 'percentage': p['percentage']} for p in positions if p['contracts'] > 0]
        except:
            return []

    async def check_order_status(self, order_id: str, symbol: str) -> Optional[Dict]:
        try:
            exchange = await self._get_exchange()
            order = await exchange.fetch_order(order_id, symbol)
            return {'id': order['id'], 'status': order['status'], 'filled': order['filled'], 'remaining': order['remaining'], 'price': order['price']}
        except Exception as e:
            logger.error(f"Failed to check order {order_id}: {e}")
            return None

broker_service = BrokerService()
