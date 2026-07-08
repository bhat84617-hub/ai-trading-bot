from .config import settings
from .database import engine, SessionLocal, get_db

try:
    from .redis_client import redis_client
except ImportError:
    from .redis_dummy import redis_client
