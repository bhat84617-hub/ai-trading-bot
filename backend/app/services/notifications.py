import asyncio
from typing import Dict, Optional
from loguru import logger
from ..core.config import settings

class NotificationService:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID

    async def send_telegram(self, message: str, parse_mode: str = "HTML") -> bool:
        if not self.bot_token or not self.chat_id:
            logger.debug("Telegram not configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": message, "parse_mode": parse_mode}
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    async def notify_signal(self, signal: Dict):
        msg = (
            f"<b>📊 TRADE SIGNAL</b>\n"
            f"<b>Symbol:</b> {signal.get('symbol', 'N/A')}\n"
            f"<b>Direction:</b> {'🟢 LONG' if signal.get('direction') == 'long' else '🔴 SHORT'}\n"
            f"<b>Entry:</b> ${signal.get('entry_price', 'N/A')}\n"
            f"<b>Stop Loss:</b> ${signal.get('stop_loss', 'N/A')}\n"
            f"<b>Take Profit:</b> ${signal.get('take_profit', 'N/A')}\n"
            f"<b>Confidence:</b> {signal.get('confidence', 0)}%\n"
            f"<b>Risk/Reward:</b> 1:{signal.get('risk_reward', 0):.2f}\n"
            f"<b>Reason:</b> {signal.get('reason', 'N/A')[:200]}"
        )
        await self.send_telegram(msg)

    async def notify_trade_execution(self, trade: Dict):
        msg = (
            f"<b>⚡ TRADE EXECUTED</b>\n"
            f"<b>Symbol:</b> {trade.get('symbol', 'N/A')}\n"
            f"<b>Direction:</b> {'🟢 LONG' if trade.get('direction') == 'long' else '🔴 SHORT'}\n"
            f"<b>Entry:</b> ${trade.get('entry_price', 'N/A')}\n"
            f"<b>Size:</b> {trade.get('quantity', 0)}\n"
            f"<b>Order ID:</b> {trade.get('order_id', 'N/A')[:16]}..."
        )
        await self.send_telegram(msg)

    async def notify_trade_result(self, trade: Dict):
        pnl = trade.get('pnl', 0)
        emoji = '🟢' if pnl >= 0 else '🔴'
        msg = (
            f"<b>{emoji} TRADE CLOSED</b>\n"
            f"<b>Symbol:</b> {trade.get('symbol', 'N/A')}\n"
            f"<b>PnL:</b> {'+' if pnl >= 0 else ''}{pnl:.2f} ({trade.get('pnl_percentage', 0):.2f}%)\n"
            f"<b>Entry:</b> ${trade.get('entry_price', 'N/A')} → <b>Exit:</b> ${trade.get('exit_price', 'N/A')}"
        )
        await self.send_telegram(msg)

    async def notify_error(self, error_msg: str):
        await self.send_telegram(f"<b>❌ ERROR</b>\n{error_msg[:500]}")

    async def notify_daily_summary(self, summary: Dict):
        msg = (
            f"<b>📈 DAILY SUMMARY</b>\n"
            f"<b>PnL:</b> {'+' if summary.get('daily_pnl', 0) >= 0 else ''}{summary.get('daily_pnl', 0):.2f}\n"
            f"<b>Win Rate:</b> {summary.get('win_rate', 0):.1f}%\n"
            f"<b>Trades:</b> {summary.get('total_trades', 0)}\n"
            f"<b>Open Positions:</b> {summary.get('open_positions', 0)}"
        )
        await self.send_telegram(msg)

notifier = NotificationService()
