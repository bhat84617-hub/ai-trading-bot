from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
import sys
import os

from .core.config import settings
from .core.database import init_db, close_db
from .core.redis_client import redis_client
from .api.routes import router

def setup_logging():
    import os
    os.makedirs("logs", exist_ok=True)
    logger.remove()
    logger.add(sys.stdout, level="DEBUG" if settings.DEBUG else "INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{name}</cyan> - <level>{message}</level>")
    logger.add("logs/trading_bot.log", rotation="10 MB", retention="7 days", level="INFO")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database init failed (will retry): {e}")
    await redis_client.connect()
    yield
    await close_db()
    await redis_client.disconnect()
    logger.info("Shutdown complete")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "version": settings.VERSION, "status": "running"}
