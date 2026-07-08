"""
Real news headlines for a symbol, used as input to the AI's sentiment call.

Previously the bot claimed to do "news analysis" but the code always passed
news="" and sentiment="neutral" to the AI — nothing was ever fetched. This
pulls real recent headlines from NewsAPI.org (https://newsapi.org, free tier
works fine for this) and hands them to the AI, which reads them and decides
bullish/bearish/neutral itself as part of its existing analysis prompt —
that's a more honest "sentiment analysis" than a hardcoded keyword list.

Get a free key at https://newsapi.org/register and set NEWS_API_KEY in .env.
Without a key, this returns "" and the AI analysis proceeds on technicals only
(same as before) rather than failing the whole scan.
"""
import httpx
from typing import Optional
from loguru import logger
from ..core.config import settings
from ..core.redis_client import redis_client

# Common ticker -> company/asset name, so search results aren't just noise on
# the raw ticker (searching "TSLA" is worse than searching "Tesla").
_SYMBOL_TO_QUERY = {
    "TSLA": "Tesla", "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Google",
    "AMZN": "Amazon", "NVDA": "Nvidia", "META": "Meta Platforms",
    "SPY": "S&P 500", "QQQ": "Nasdaq 100",
    "BTC/USD": "Bitcoin", "BTC/USDT": "Bitcoin",
    "ETH/USD": "Ethereum", "ETH/USDT": "Ethereum",
}


class NewsService:
    def __init__(self):
        self.api_key = settings.NEWS_API_KEY

    def _query_for(self, symbol: str) -> str:
        return _SYMBOL_TO_QUERY.get(symbol.upper(), symbol.replace("/", " "))

    async def get_headlines(self, symbol: str, limit: int = 5) -> str:
        if not self.api_key:
            logger.debug("NEWS_API_KEY not set — skipping news fetch, AI will analyze on technicals only.")
            return ""

        cache_key = f"news:{symbol}"
        cached = await redis_client.get(cache_key)
        if cached:
            return cached

        query = self._query_for(symbol)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "q": query,
                        "sortBy": "publishedAt",
                        "language": "en",
                        "pageSize": limit,
                        "apiKey": self.api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                articles = data.get("articles", [])
                if not articles:
                    return ""
                lines = []
                for a in articles[:limit]:
                    title = a.get("title", "").strip()
                    source = (a.get("source") or {}).get("name", "")
                    if title:
                        lines.append(f"- [{source}] {title}")
                text = "\n".join(lines)
                await redis_client.set(cache_key, text, ttl=900)  # news doesn't need to be re-fetched every minute
                return text
        except Exception as e:
            logger.error(f"News fetch failed for {symbol} ({query}): {e}")
            return ""


news_service = NewsService()
