from datetime import datetime
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from app.models.user_model import User
from app.schemas.user_schema import UserCreate, UserUpdate
from app.crud.base_crud import CRUDBase


class UserCRUD(CRUDBase[User, UserCreate, UserUpdate]):

    async def get_by_id(self, db: AsyncSession, user_id: str | UUID) -> User | None:
        """Get user by ID (string or UUID)."""
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        return await self.get(db, id=user_id)

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        result = await db.exec(select(User).where(User.email == email))
        return result.first()

    async def get_by_google_id(self, db: AsyncSession, google_id: str) -> User | None:
        result = await db.exec(select(User).where(User.google_id == google_id))
        return result.first()

    async def get_by_google_id_or_email(
        self, db: AsyncSession, google_id: str, email: str
    ) -> User | None:
        result = await db.exec(
            select(User).where((User.google_id == google_id) | (User.email == email))
        )
        return result.first()

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        db_obj = User(**obj_in.model_dump())
        db.add(db_obj)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        await db.refresh(db_obj)
        return db_obj

    async def update_google_credentials(
        self, db: AsyncSession, *, user: User, credentials_json: str
    ) -> User:
        user.google_credentials_json = credentials_json
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def update_refresh_token(
        self,
        db: AsyncSession,
        *,
        user: User,
        refresh_token: str | None,
        expires: datetime | None,
    ) -> User:
        """Update user's refresh token and expiry."""
        user.refresh_token = refresh_token
        user.refresh_token_expires = expires
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def get_by_refresh_token(self, db: AsyncSession, refresh_token: str) -> User | None:
        """Get user by refresh token."""
        result = await db.exec(select(User).where(User.refresh_token == refresh_token))
        return result.first()


user_crud = UserCRUD(User)