from typing import TYPE_CHECKING, Optional, Any
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON
from uuid import UUID

from .base_model import BaseUUIDModel
from .enums import ProcessingStatus

if TYPE_CHECKING:
    from .user_model import User

class MailBase(SQLModel):
    image_s3_key: str = Field(index=True)
    image_url: str 
    
    status: ProcessingStatus = Field(default=ProcessingStatus.PENDING)
    
    receiver_name: str | None = None
    receiver_address: str | None = None
    receiver_pincode: str | None = Field(default=None, index=True) 
    
    sender_name: str | None = None
    sender_address: str | None = None
    sender_pincode: str | None = None
    
    assigned_sorting_center: str | None = None

class Mail(BaseUUIDModel, MailBase, table=True):
    __tablename__ = "mails"
    
    raw_ai_response: dict | list | None = Field(default=None, sa_column=Column(JSON))

    user_id: UUID = Field(foreign_key="users.id", index=True)
    user: "User" = Relationship(back_populates="mails")
    