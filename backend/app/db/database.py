from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import settings

# Pool configuration for serverless databases (Supabase/NeonDB)
DB_POOL_SIZE = 5
MAX_OVERFLOW = 10
POOL_RECYCLE = 300  # Recycle connections after 5 minutes
POOL_PRE_PING = True  # Check connection health before using

# Create the async engine with connection health checks
engine = create_async_engine(
    str(settings.ASYNC_DATABASE_URI),
    echo=False,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=DB_POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,
)

# Create a sessionmaker factory
# This factory will create new AsyncSession objects when called
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)