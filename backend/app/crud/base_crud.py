from typing import Any, Generic, TypeVar, List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import exc
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType]):
        """
        Base CRUD object with default methods to Create, Read, Update, Delete.

        Parameters:

        model: A SQLModel model class
        """
        self.model = model

    async def get(self, db: AsyncSession, id: Any) -> ModelType | None:
        """
        Get a single object by its primary key.
        """
        query = select(self.model).where(self.model.id == id)
        result = await db.exec(query)
        return result.first()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        Get multiple objects with offset and limit.
        """
        query = select(self.model).offset(skip).limit(limit)
        result = await db.exec(query)
        return result.all()

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Create a new object in the database.
        """
        
        db_obj = self.model.model_validate(obj_in)
        
        try:
            db.add(db_obj)
            await db.commit()
        except exc.IntegrityError:
            await db.rollback()

            raise HTTPException(
                status_code=409,
                detail="Resource with a conflicting unique field already exists.",
            )
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: ModelType, obj_in: UpdateSchemaType | dict
    ) -> ModelType:
        """
        Update an existing database object.
        """

        if isinstance(obj_in, BaseModel):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: UUID) -> ModelType:
        """
        Remove an object from the database by its id.
        """
        obj = await self.get(db, id=id)
        if not obj:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        await db.delete(obj)
        await db.commit()
        return obj