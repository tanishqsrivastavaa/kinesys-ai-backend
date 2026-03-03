from pydantic import BaseModel, EmailStr
from uuid import UUID


class UserCreate(BaseModel):
    """Internal schema for creating user from Google OAuth"""
    email: EmailStr
    google_id: str
    username: str
    full_name: str | None = None
    picture_url: str | None = None


class UserRead(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    full_name: str | None = None
    picture_url: str | None = None
    has_google_calendar: bool = False


class UserUpdate(BaseModel):
    username: str | None = None
    full_name: str | None = None


class UserListItem(BaseModel):
    """Schema for user in dropdown lists."""
    id: UUID
    name: str  # full_name or username
    email: EmailStr
    avatar: str | None = None


class UserListResponse(BaseModel):
    """Response for users list."""
    data: list[UserListItem]
    total_count: int