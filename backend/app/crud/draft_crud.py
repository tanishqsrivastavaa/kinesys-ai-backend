from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from uuid import UUID
from app.models.draft_model import Draft
from app.schemas.draft_schema import DraftCreate

class DraftCRUD:
    def __init__(self, model):
        self.model = model

    async def create(self, db: AsyncSession, *, obj_in: DraftCreate, user_id: UUID) -> Draft:
        db_obj = Draft(draft=obj_in.draft, summary=obj_in.summary, user_id=user_id)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get(self, db: AsyncSession, id: UUID, user_id: UUID) -> Draft | None:
        result = await db.exec(
            select(Draft).where(Draft.id == id, Draft.user_id == user_id)
        )
        return result.first()

    async def remove(self, db: AsyncSession, id: UUID, user_id: UUID) -> Draft | None:
        obj = await self.get(db, id, user_id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj
    
    async def get_drafts_by_user(
        self, db: AsyncSession, user_id: UUID, limit: int = 100
    ):
        result = await db.exec(
            select(self.model)
            .where(self.model.user_id == user_id)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return result.all()
    
    async def get_draft_summary(
            self, db:AsyncSession, user_id: UUID, draft_id: UUID 
    ):
        result = await db.exec(
            select(self.model.summary)
            .where(self.model.user_id == user_id, self.model.id == draft_id)
        )
        return result.first()

draft_crud = DraftCRUD(Draft)