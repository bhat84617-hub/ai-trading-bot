from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import settings
from loguru import logger

DB_URL = settings.DATABASE_URL or ""
if "postgresql" not in DB_URL:
    DB_URL = "sqlite+aiosqlite:///./trading_bot.db"

engine = create_async_engine(DB_URL, echo=settings.DEBUG)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database ready")
    except Exception as e:
        logger.warning(f"DB init: {e}")

async def close_db():
    await engine.dispose()
