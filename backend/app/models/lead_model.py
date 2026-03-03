"""Lead module models for CRM."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import DateTime, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.base_model import BaseUUIDModel, SoftDeleteMixin, utc_now
from app.models.enums import LeadSource, LeadStage, LeadTemperature

if TYPE_CHECKING:
    from app.models.user_model import User


class LeadTagLink(SQLModel, table=True):
    """Junction table for Lead-Tag many-to-many relationship."""

    __tablename__ = "lead_tags"

    lead_id: UUID = Field(foreign_key="leads.id", primary_key=True, index=True)
    tag_id: UUID = Field(foreign_key="tags.id", primary_key=True, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
    )


class Tag(BaseUUIDModel, table=True):
    """Tag model for categorizing leads."""

    __tablename__ = "tags"

    name: str = Field(max_length=50, index=True)
    color: str = Field(default="#3B82F6", max_length=7)
    user_id: UUID = Field(foreign_key="users.id", index=True)

    # Relationships
    leads: list["Lead"] = Relationship(
        back_populates="tags",
        link_model=LeadTagLink,
    )

    __table_args__ = (
        Index("ix_tags_user_name", "user_id", "name", unique=True),
    )


class LeadBase(SQLModel):
    """Base fields for Lead model."""

    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    email: str | None = Field(default=None, max_length=255, index=True)
    phone: str | None = Field(default=None, max_length=50)
    mobile_no: str | None = Field(default=None, max_length=50)
    company: str | None = Field(default=None, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=500)
    job_title: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=100)
    # Store enums as VARCHAR - Python enums validate, DB stores string value
    source: str = Field(default=LeadSource.OTHER.value, sa_type=String(50))
    stage: str = Field(default=LeadStage.NEW.value, sa_type=String(50), index=True)
    temperature: str = Field(default=LeadTemperature.COLD.value, sa_type=String(20))
    lead_score: int = Field(default=0, ge=0, le=100)
    annual_revenue: str | None = Field(default=None, max_length=50)
    employee_count: str | None = Field(default=None, max_length=50)
    territory: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, sa_type=Text)


class Lead(BaseUUIDModel, LeadBase, SoftDeleteMixin, table=True):
    """Lead model representing a potential customer."""

    __tablename__ = "leads"

    user_id: UUID = Field(foreign_key="users.id", index=True)
    assigned_to: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    last_activity_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    interests: list[str] = Field(
        default_factory=list,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": "[]"},
    )
    custom_fields: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        sa_column_kwargs={"server_default": "{}"},
    )

    # Relationships
    tags: list[Tag] = Relationship(
        back_populates="leads",
        link_model=LeadTagLink,
    )
    stage_history: list["LeadStageHistory"] = Relationship(back_populates="lead")
    owner: "User" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Lead.user_id]"},
    )
    assignee: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Lead.assigned_to]"},
    )
    # Note: Calendar events are linked via CalendarEventLink.lead_id (no ORM relationship)

    __table_args__ = (
        Index("ix_leads_user_stage", "user_id", "stage"),
        Index("ix_leads_user_active", "user_id", "is_active"),
    )

    @property
    def lead_name(self) -> str:
        """Computed full name of the lead."""
        return f"{self.first_name} {self.last_name}"

    @property
    def modified(self) -> datetime:
        """Alias for updated_at for backward compatibility."""
        return self.updated_at or self.created_at

    @property
    def status(self) -> str:
        """Status display name derived from stage."""
        try:
            return LeadStage(self.stage).label
        except ValueError:
            return self.stage.capitalize() if self.stage else "Unknown"


class LeadStageHistory(BaseUUIDModel, table=True):
    """Tracks stage changes for a lead."""

    __tablename__ = "lead_stage_history"

    lead_id: UUID = Field(foreign_key="leads.id", index=True)
    from_stage: str | None = Field(default=None, sa_type=String(50))
    to_stage: str = Field(sa_type=String(50))
    changed_by: UUID = Field(foreign_key="users.id", index=True)
    changed_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
    )
    notes: str | None = Field(default=None, sa_type=Text)

    # Relationships
    lead: Lead = Relationship(back_populates="stage_history")
