"""
FastAPI application entry point.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.scheduler import init_scheduler, shutdown_scheduler
from app.routers import watchlist, account, trades, risk, system, backtest, scan

# Setup logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events to manage background scheduler."""
    logger.info("Initializing AlgoTrade Bot backend...")
    
    # Try initializing background jobs
    try:
        init_scheduler()
    except Exception as e:
        logger.error(f"Failed to start scheduler on startup: {e}")
        
    yield
    
    logger.info("Shutting down AlgoTrade Bot backend...")
    shutdown_scheduler()


# Create FastAPI application instance
app = FastAPI(
    title="AlgoTrade Bot Platform API",
    description="Backend engines and broker integration layer for personal algorithmic trading.",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend connection
settings = get_settings()
origins = [
    settings.frontend_url,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(watchlist.router)
app.include_router(account.router)
app.include_router(trades.router)
app.include_router(risk.router)
app.include_router(system.router)
app.include_router(backtest.router)
app.include_router(scan.router)


@app.get("/health")
def health_check():
    """Simple API check."""
    return {"status": "healthy", "service": "algotrade-bot-backend"}
