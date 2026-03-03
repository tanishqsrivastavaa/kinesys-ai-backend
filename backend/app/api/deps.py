from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from collections.abc import AsyncGenerator

from app.db.database import AsyncSessionLocal
from app.core.config import settings, ModeEnum
from app.core.jwt import decode_access_token
from app.models.user_model import User

auth_scheme = APIKeyHeader(name="Authorization", auto_error=False)

# Dev user ID - consistent across restarts for dev testing
DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_or_create_dev_user(db: AsyncSession) -> User:
    """Get or create a development test user."""
    user = await db.get(User, DEV_USER_ID)
    if not user:
        user = User(
            id=DEV_USER_ID,
            email="dev@localhost.test",
            username="dev_user",
            full_name="Development User",
            google_id="dev_google_id",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def get_current_user(
    token: str | None = Depends(auth_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # In development mode, allow unauthenticated access with a dev user
    if settings.MODE == ModeEnum.development and not token:
        return await get_or_create_dev_user(db)

    # Require token in production/testing
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )

    # Strip "Bearer " prefix if present (standard OAuth2 format)
    if token.startswith("Bearer "):
        token = token[7:]

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication",
        )
    user = await db.get(User, payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user