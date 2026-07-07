from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "AI Trading Bot"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/trading_bot")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    CLAUDE_API_KEY: Optional[str] = os.getenv("CLAUDE_API_KEY")
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "openai")
    AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4-turbo")

    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")

    BROKER_API_KEY: Optional[str] = os.getenv("BROKER_API_KEY")
    BROKER_SECRET_KEY: Optional[str] = os.getenv("BROKER_SECRET_KEY")
    BROKER_PAPER_KEY: Optional[str] = os.getenv("BROKER_PAPER_KEY", "paper")
    BROKER_PAPER_SECRET: Optional[str] = os.getenv("BROKER_PAPER_SECRET", "paper")
    BROKER_NAME: str = os.getenv("BROKER_NAME", "alpaca")

    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-key-change-in-production")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "encryption-key-32-chars-long!")

    MAX_RISK_PER_TRADE: float = float(os.getenv("MAX_RISK_PER_TRADE", "2.0"))
    MAX_DAILY_LOSS: float = float(os.getenv("MAX_DAILY_LOSS", "5.0"))
    MAX_DRAWDOWN: float = float(os.getenv("MAX_DRAWDOWN", "20.0"))
    MAX_OPEN_POSITIONS: int = int(os.getenv("MAX_OPEN_POSITIONS", "5"))
    MIN_CONFIDENCE_SCORE: float = float(os.getenv("MIN_CONFIDENCE_SCORE", "65.0"))
    MIN_RISK_REWARD: float = float(os.getenv("MIN_RISK_REWARD", "2.0"))

    TRADE_MODE: str = os.getenv("TRADE_MODE", "paper")

    SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "5"))
    WATCHLIST_SYMBOLS: str = os.getenv("WATCHLIST_SYMBOLS", "BTC/USD,ETH/USD,TSLA,AAPL,MSFT,GOOGL,AMZN,NVDA,META,SPY,QQQ")

    DATABASE_URL_SYNC: str = os.getenv("DATABASE_URL_SYNC", "postgresql://postgres:postgres@localhost:5432/trading_bot")

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
