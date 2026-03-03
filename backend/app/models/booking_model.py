"""Booking model for voice agent appointment scheduling."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base_model import BaseUUIDModel, SoftDeleteMixin


class BookingStatus(str, Enum):
    """Status of a booking."""
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Booking(BaseUUIDModel, SoftDeleteMixin, table=True):
    """
    Booking model for storing appointment data.

    Stores appointment datetime in UTC with the original timezone preserved
    for display purposes.
    """
    __tablename__ = "bookings"

    # Appointment details - stored in UTC
    appointment_datetime: datetime = Field(
        sa_type=DateTime(timezone=True),
        index=True,
        nullable=False,
    )
    timezone: str = Field(max_length=50, nullable=False)  # e.g., "America/New_York"

    # Contact information
    first_name: str = Field(max_length=100, nullable=False)
    last_name: str = Field(max_length=100, nullable=False)
    email: str = Field(max_length=255, nullable=False, index=True)
    phone: str = Field(max_length=50, nullable=False)

    # Optional link to lead/contact (no FK constraint - may reference external CRM)
    contact_id: UUID | None = Field(default=None, nullable=True, index=True)

    # Booking status
    status: str = Field(default=BookingStatus.CONFIRMED.value, max_length=20)

    # For idempotency - unique constraint on email + appointment slot
    __table_args__ = (
        UniqueConstraint(
            "appointment_datetime",
            "is_active",
            name="uq_booking_slot_active",
        ),
    )

    @property
    def full_name(self) -> str:
        """Return full name of the contact."""
        return f"{self.first_name} {self.last_name}"
