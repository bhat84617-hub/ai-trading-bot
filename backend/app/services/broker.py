import ccxt.async_support as ccxt
from typing import Dict, Optional, List
from loguru import logger
from ..core.config import settings
from .brokers import DhanBroker, OctaFXBroker, AlpacaBroker

# Broker exchange classes actually available in ccxt — crypto exchanges only.
# (Bug fix history: this dict used to also list 'alpaca'/'tradier'/'oanda' as
# if ccxt supported them. It never did — ccxt is crypto-only. Stocks now go
# through AlpacaBroker's real REST API instead, see below.)
_CCXT_EXCHANGE_IDS = {
    'binance': 'binance', 'bybit': 'bybit', 'okx': 'okx',
    'kucoin': 'kucoin', 'kraken': 'kraken', 'coinbase': 'coinbase',
    'gateio': 'gate', 'gate': 'gate',
    'bitget': 'bitget', 'mexc': 'mexc', 'huobi': 'huobi',
    'bitfinex': 'bitfinex', 'cryptocom': 'cryptocom',
    'gemini': 'gemini', 'bitmart': 'bitmart', 'lbank': 'lbank',
    'poloniex': 'poloniex', 'ascendex': 'ascendex', 'coindcx': 'coindcx',
}

SUPPORTED_CRYPTO_EXCHANGES = {}
for name, ccxt_name in _CCXT_EXCHANGE_IDS.items():
    if hasattr(ccxt, ccxt_name):
        SUPPORTED_CRYPTO_EXCHANGES[name] = getattr(ccxt, ccxt_name)

# What the frontend's broker picker shows — includes non-ccxt custom brokers too.
SUPPORTED_EXCHANGES = {**SUPPORTED_CRYPTO_EXCHANGES, 'dhan': 'custom_dhan', 'octafx': 'custom_octafx', 'alpaca': 'custom_alpaca'}


class BrokerService:
    """
    Routes every order/balance/position call based on asset class:
      - Symbol has '/' (e.g. BTC/USDT)      -> crypto exchange (ccxt), default Bybit
      - Plain ticker (e.g. TSLA, AAPL)      -> Alpaca (native REST API)
      - India-specific overrides (Dhan/OctaFX) available via switch_broker()
        for symbols you explicitly want routed there.

    This exists because a single global "BROKER_NAME" can't serve both a
    stock account and a crypto account at the same time — you have keys for
    both Alpaca and Bybit, so both should work simultaneously without manual
    switching for every trade.
    """

    def __init__(self):
        self.is_live = settings.TRADE_MODE == "live"
        self._crypto_broker_name = settings.CRYPTO_BROKER_NAME or "bybit"
        self._crypto_exchange = None
        self._alpaca: Optional[AlpacaBroker] = None
        self._override_broker: Optional[str] = None  # e.g. 'dhan', 'octafx' if user explicitly switches

    async def switch_broker(self, broker_name: str):
        """Manual override — e.g. force everything through Dhan/OctaFX, or pick a different crypto exchange."""
        name = broker_name.lower()
        if name in ('dhan', 'octafx'):
            self._override_broker = name
        elif name in SUPPORTED_CRYPTO_EXCHANGES:
            self._crypto_broker_name = name
            self._crypto_exchange = None
            self._override_broker = None
        elif name == 'alpaca':
            self._override_broker = None  # alpaca is already the default for stocks
        else:
            raise ValueError(f"Unsupported broker '{broker_name}'")
        logger.info(f"Broker switched: crypto={self._crypto_broker_name} override={self._override_broker}")

    def _is_crypto_symbol(self, symbol: str) -> bool:
        return '/' in symbol.upper()

    def _get_alpaca(self) -> Optional[AlpacaBroker]:
        if not settings.ALPACA_API_KEY or not settings.ALPACA_SECRET_KEY:
            logger.error("ALPACA_API_KEY / ALPACA_SECRET_KEY not set in .env — stock orders will fail.")
            return None
        if self._alpaca is None:
            self._alpaca = AlpacaBroker(
                api_key=settings.ALPACA_API_KEY,
                secret_key=settings.ALPACA_SECRET_KEY,
                is_paper=not self.is_live,
            )
        return self._alpaca

    async def _get_crypto_exchange(self):
        if self._crypto_exchange is not None:
            return self._crypto_exchange
        exchange_class = SUPPORTED_CRYPTO_EXCHANGES.get(self._crypto_broker_name)
        if not exchange_class:
            raise ValueError(f"Crypto broker '{self._crypto_broker_name}' not available in this ccxt install.")

        api_key = settings.CRYPTO_API_KEY or settings.BROKER_API_KEY
        secret = settings.CRYPTO_SECRET_KEY or settings.BROKER_SECRET_KEY
        if not api_key or not secret:
            logger.error(f"CRYPTO_API_KEY / CRYPTO_SECRET_KEY not set — {self._crypto_broker_name} orders will fail.")

        config = {'apiKey': api_key, 'secret': secret, 'enableRateLimit': True}
        if not self.is_live:
            config['options'] = {'defaultType': 'spot'}
        self._crypto_exchange = exchange_class(config)
        # Bybit/most ccxt exchanges use `set_sandbox_mode` for testnet, not a 'sandbox' kwarg.
        if not self.is_live and hasattr(self._crypto_exchange, 'set_sandbox_mode'):
            try:
                self._crypto_exchange.set_sandbox_mode(True)
            except Exception as e:
                logger.warning(f"Could not enable sandbox/testnet mode for {self._crypto_broker_name}: {e}")
        return self._crypto_exchange

    async def _get_custom_broker(self):
        if self._override_broker == 'dhan':
            return DhanBroker(
                client_id=settings.BROKER_API_KEY or "dhan_client_id",
                access_token=settings.BROKER_SECRET_KEY or "dhan_token",
                is_paper=not self.is_live,
            )
        if self._override_broker == 'octafx':
            return OctaFXBroker(
                api_key=settings.BROKER_API_KEY or "octafx_key",
                account_id=settings.BROKER_SECRET_KEY or "octafx_account",
                is_paper=not self.is_live,
            )
        return None

    async def _route(self, symbol: str):
        """Pick the right broker adapter for this symbol."""
        if self._override_broker:
            custom = await self._get_custom_broker()
            if custom:
                return custom
        if self._is_crypto_symbol(symbol):
            return await self._get_crypto_exchange()
        alpaca = self._get_alpaca()
        if not alpaca:
            raise ValueError("Alpaca not configured — set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env")
        return alpaca

    # ---- Unified account balance across both brokers ----
    async def get_account_balance(self) -> float:
        total = 0.0
        got_any = False

        alpaca = self._get_alpaca()
        if alpaca:
            try:
                total += await alpaca.get_account_balance()
                got_any = True
            except Exception as e:
                logger.error(f"Alpaca balance fetch failed: {e}")

        try:
            exchange = await self._get_crypto_exchange()
            balance = await exchange.fetch_balance()
            usd = balance.get('total', {}).get('USDT') or balance.get('total', {}).get('USD') or 0
            total += float(usd)
            got_any = True
        except Exception as e:
            logger.error(f"Crypto balance fetch failed: {e}")

        if not got_any:
            logger.warning("No broker configured/reachable — returning 0 balance, not a fake number.")
            return 0.0
        return total

    async def place_order(self, symbol: str, side: str, order_type: str, amount: float,
                           price: Optional[float] = None, params: Optional[Dict] = None) -> Optional[Dict]:
        try:
            broker = await self._route(symbol)

            if isinstance(broker, AlpacaBroker):
                return await broker.place_order(symbol, side, order_type, amount, price, params)

            if isinstance(broker, DhanBroker):
                return await broker.place_order(symbol, side, amount, order_type.upper())

            if isinstance(broker, OctaFXBroker):
                return await broker.place_order(symbol, side, amount, order_type.lower())

            # ccxt crypto exchange
            order = await broker.create_order(symbol, order_type, side, amount, price, params or {})
            logger.info(f"Order placed: {side} {amount} {symbol} @ {price}")
            return {
                'id': order.get('id', ''), 'symbol': order.get('symbol', symbol),
                'side': order.get('side', side), 'amount': order.get('amount', amount),
                'price': order.get('price', price), 'status': order.get('status', 'open'),
                'filled': order.get('filled', 0), 'remaining': order.get('remaining', amount),
                'timestamp': order.get('timestamp'),
            }
        except Exception as e:
            logger.error(f"Order failed for {symbol}: {e}")
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
            broker = await self._route(symbol)
            if isinstance(broker, AlpacaBroker):
                return await broker.cancel_order(order_id, symbol)
            await broker.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        results = []
        alpaca = self._get_alpaca()
        if alpaca and (not symbol or not self._is_crypto_symbol(symbol)):
            results.extend(await alpaca.get_open_orders(symbol))
        if not symbol or self._is_crypto_symbol(symbol):
            try:
                exchange = await self._get_crypto_exchange()
                orders = await exchange.fetch_open_orders(symbol)
                results.extend([{
                    'id': o['id'], 'symbol': o['symbol'], 'side': o['side'],
                    'amount': o['amount'], 'price': o['price'], 'status': o['status'],
                    'timestamp': o['timestamp'],
                } for o in orders])
            except Exception as e:
                logger.error(f"Failed to fetch crypto open orders: {e}")
        return results

    async def get_positions(self) -> List[Dict]:
        results = []
        alpaca = self._get_alpaca()
        if alpaca:
            results.extend(await alpaca.get_positions())
        try:
            exchange = await self._get_crypto_exchange()
            positions = await exchange.fetch_positions()
            results.extend([{
                'symbol': p['symbol'], 'side': 'long' if p['side'] == 'long' else 'short',
                'contracts': p['contracts'], 'entry_price': p['entryPrice'],
                'current_price': p['currentPrice'], 'pnl': p['pnl'], 'percentage': p['percentage'],
            } for p in positions if p.get('contracts', 0) > 0])
        except Exception as e:
            logger.error(f"Failed to fetch crypto positions: {e}")
        return results

    async def check_order_status(self, order_id: str, symbol: str) -> Optional[Dict]:
        try:
            broker = await self._route(symbol)
            if isinstance(broker, AlpacaBroker):
                return await broker.check_order_status(order_id, symbol)
            order = await broker.fetch_order(order_id, symbol)
            return {
                'id': order['id'], 'status': order['status'],
                'filled': order['filled'], 'remaining': order['remaining'], 'price': order['price'],
            }
        except Exception as e:
            logger.error(f"Failed to check order {order_id}: {e}")
            return None


broker_service = BrokerService()
