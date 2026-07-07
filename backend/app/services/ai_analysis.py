import json
from typing import Dict, Optional, List, Tuple
from loguru import logger
import httpx
from ..core.config import settings
from ..core.redis_client import redis_client

class AIAnalysisService:
    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.model = settings.AI_MODEL
        self.openai_key = settings.OPENAI_API_KEY
        self.claude_key = settings.CLAUDE_API_KEY
        self.openrouter_key = settings.OPENROUTER_API_KEY

    async def _call_openai(self, messages: List[Dict], temperature: float = 0.3) -> Optional[str]:
        if not self.openai_key:
            return None
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.openai_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages, "temperature": temperature}
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_openrouter(self, messages: List[Dict], temperature: float = 0.3) -> Optional[str]:
        if not self.openrouter_key:
            return None
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.openrouter_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages, "temperature": temperature}
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_claude(self, messages: List[Dict], temperature: float = 0.3) -> Optional[str]:
        if not self.claude_key:
            return None
        system = messages[0]["content"] if messages[0]["role"] == "system" else ""
        user_msgs = [m for m in messages if m["role"] == "user"]
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self.claude_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                json={"model": "claude-3-opus-20240229", "system": system, "messages": user_msgs, "temperature": temperature, "max_tokens": 2000}
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

    async def analyze_signal(self, symbol: str, indicators: Dict, news: str = "", sentiment: str = "neutral") -> Optional[Dict]:
        cache_key = f"ai_analysis:{symbol}:{hash(str(indicators))}"
        cached = await redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        prompt = self._build_analysis_prompt(symbol, indicators, news, sentiment)
        messages = [
            {"role": "system", "content": "You are an expert quantitative trader and AI trading analyst. Analyze the market data and provide a trading decision in JSON format only. No markdown, no explanation outside JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            if self.provider == "openai" and self.openai_key:
                response = await self._call_openai(messages)
            elif self.provider == "claude" and self.claude_key:
                response = await self._call_claude(messages)
            elif self.openrouter_key:
                response = await self._call_openrouter(messages)
            else:
                logger.warning("No AI provider configured, using rule-based fallback")
                return self._rule_based_analysis(symbol, indicators)

            if response:
                result = self._parse_response(response)
                if result:
                    await redis_client.set(cache_key, result, ttl=60)
                    return result
            return self._rule_based_analysis(symbol, indicators)
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return self._rule_based_analysis(symbol, indicators)

    def _build_analysis_prompt(self, symbol: str, indicators: Dict, news: str, sentiment: str) -> str:
        return f"""Analyze {symbol} for a trading opportunity using this data:

TECHNICAL INDICATORS:
- Price: ${indicators.get('current_price', 'N/A')}
- RSI (14): {indicators.get('rsi', 'N/A')}
- MACD: Line={indicators.get('macd_line', 'N/A')}, Signal={indicators.get('macd_signal', 'N/A')}, Histogram={indicators.get('macd_histogram', 'N/A')}
- Bollinger Bands: Upper={indicators.get('bb_upper', 'N/A')}, Mid={indicators.get('bb_middle', 'N/A')}, Lower={indicators.get('bb_lower', 'N/A')}
- ATR (14): {indicators.get('atr', 'N/A')}
- VWAP: {indicators.get('vwap', 'N/A')}
- EMA 9: {indicators.get('ema_9', 'N/A')}, EMA 21: {indicators.get('ema_21', 'N/A')}, EMA 50: {indicators.get('ema_50', 'N/A')}, EMA 200: {indicators.get('ema_200', 'N/A')}
- Trend: {indicators.get('trend', 'N/A')}
- Momentum: {indicators.get('momentum', 'N/A')}
- Volume Ratio: {indicators.get('volume_ratio', 'N/A')}
- Support: {indicators.get('support_1', 'N/A')}, Resistance: {indicators.get('resistance_1', 'N/A')}
- Breakout: {indicators.get('breakout', 'N/A')} ({indicators.get('breakout_type', 'N/A')})
- Liquidity Score: {indicators.get('liquidity_score', 'N/A')}
- Candlestick Patterns: {json.dumps(indicators.get('patterns', {}))}

NEWS: {news if news else 'No recent news'}
SENTIMENT: {sentiment}

Return a VALID JSON object (no markdown) with:
{{
  "direction": "long" or "short" or "neutral",
  "confidence_score": (0-100 number),
  "entry_price": (number),
  "stop_loss": (number),
  "take_profit": (number),
  "risk_reward_ratio": (number),
  "risk_percentage": (number, 0.5-2.0),
  "reason": "clear explanation of the analysis",
  "trade_explanation": "detailed explanation of why this trade is recommended",
  "news_sentiment": "bullish/bearish/neutral",
  "market_context": "current market structure analysis"
}}

If confidence is below {settings.MIN_CONFIDENCE_SCORE}, set direction to "neutral"."""

    def _parse_response(self, response: str) -> Optional[Dict]:
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("\n", 1)[0]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            result = json.loads(cleaned)
            required = ["direction", "confidence_score", "entry_price", "stop_loss", "take_profit", "reason"]
            if all(k in result for k in required):
                return result
            logger.warning(f"AI response missing required fields: {result}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}\nResponse: {response[:500]}")
            return None

    def _rule_based_analysis(self, symbol: str, indicators: Dict) -> Dict:
        confidence = 50
        direction = "neutral"
        price = indicators.get("current_price", 0)
        rsi = indicators.get("rsi", 50)
        trend = indicators.get("trend", "neutral")
        vol_ratio = indicators.get("volume_ratio", 1)
        support = indicators.get("support_1", price * 0.95)
        resistance = indicators.get("resistance_1", price * 1.05)
        atr = indicators.get("atr", price * 0.02)

        if rsi < 30 and trend == "bullish":
            direction = "long"
            confidence = 65
            reason = "Oversold with bullish trend"
        elif rsi > 70 and trend == "bearish":
            direction = "short"
            confidence = 65
            reason = "Overbought with bearish trend"
        elif vol_ratio > 1.5 and indicators.get("breakout"):
            direction = "long" if indicators["breakout_type"] == "bullish_breakout" else "short"
            confidence = 60
            reason = f"High volume {indicators.get('breakout_type', 'breakout')}"
        else:
            return {
                "direction": "neutral", "confidence_score": 0, "entry_price": price,
                "stop_loss": price * 0.95, "take_profit": price * 1.05,
                "risk_reward_ratio": 1.0, "risk_percentage": 0,
                "reason": "No clear signal from rule-based analysis",
                "trade_explanation": "No trade", "news_sentiment": "neutral",
                "market_context": "Not enough confluence for a trade"
            }

        if direction == "long":
            sl = price - (atr * 2)
            tp = price + (atr * 3)
        else:
            sl = price + (atr * 2)
            tp = price - (atr * 3)

        risk_reward = abs(tp - price) / abs(sl - price) if abs(sl - price) > 0 else 1
        risk_pct = min(settings.MAX_RISK_PER_TRADE, 1.0)

        return {
            "direction": direction, "confidence_score": confidence,
            "entry_price": round(price, 2), "stop_loss": round(sl, 2),
            "take_profit": round(tp, 2), "risk_reward_ratio": round(risk_reward, 2),
            "risk_percentage": risk_pct, "reason": reason,
            "trade_explanation": f"{direction.upper()} signal: {reason}",
            "news_sentiment": "neutral",
            "market_context": f"{trend.upper()} trend with RSI at {rsi}"
        }

ai_service = AIAnalysisService()
