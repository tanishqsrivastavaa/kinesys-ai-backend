from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr

from .base_model import BaseUUIDModel

if TYPE_CHECKING:
    from .mail_model import Mail
    from .calendar_event_link_model import CalendarEventLink


class UserBase(SQLModel):
    username: str = Field(index=True)
    email: EmailStr = Field(unique=True, index=True)


class User(BaseUUIDModel, UserBase, table=True):
    __tablename__ = "users"

    # Google OAuth fields
    google_id: str = Field(unique=True, index=True)
    full_name: str | None = Field(default=None)
    picture_url: str | None = Field(default=None)
    google_credentials_json: str | None = Field(default=None)  # Serialized Google credentials

    # JWT Refresh token fields
    refresh_token: str | None = Field(default=None, index=True)
    refresh_token_expires: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # Must be timezone-aware to match UTC datetimes
    )

    # Relationships
    # mails: list["Mail"] = Relationship(
    #     back_populates="user", sa_relationship_kwargs={"cascade": "all, delete"}
    # )
    calendar_event_links: list["CalendarEventLink"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"cascade": "all, delete"}
    )
