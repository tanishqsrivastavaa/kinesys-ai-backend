"""Pydantic schemas for booking endpoints."""

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ============== Request Schemas ==============

class BookingCreate(BaseModel):
    """Schema for creating a booking."""

    appointmentDate: str = Field(
        description="Appointment date in YYYY-MM-DD format",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        examples=["2026-01-25"],
    )
    appointmentTime: str = Field(
        description="Appointment time in HH:MM format (24-hour)",
        pattern=r"^\d{2}:\d{2}$",
        examples=["09:00", "14:30"],
    )
    timeZone: str = Field(
        description="IANA timezone identifier",
        examples=["America/New_York", "Europe/London", "Asia/Tokyo"],
    )
    firstName: str = Field(max_length=100, min_length=1)
    lastName: str = Field(max_length=100, min_length=1)
    email: EmailStr
    phone: str = Field(max_length=50, min_length=1)
    contactId: UUID | None = Field(default=None, description="Optional lead/contact UUID")

    @field_validator("timeZone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate that the timezone is a valid IANA timezone."""
        try:
            ZoneInfo(v)
            return v
        except ZoneInfoNotFoundError:
            raise ValueError(f"Invalid timezone: {v}. Use IANA timezone format (e.g., 'America/New_York')")

    @field_validator("appointmentDate")
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Validate date format and ensure it's not in the past."""
        try:
            parsed_date = datetime.strptime(v, "%Y-%m-%d").date()
            if parsed_date < date.today():
                raise ValueError("Appointment date cannot be in the past")
            return v
        except ValueError as e:
            if "does not match format" in str(e):
                raise ValueError("Invalid date format. Use YYYY-MM-DD")
            raise

    @field_validator("appointmentTime")
    @classmethod
    def validate_time(cls, v: str) -> str:
        """Validate time format."""
        try:
            hour, minute = map(int, v.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time")
            return v
        except (ValueError, AttributeError):
            raise ValueError("Invalid time format. Use HH:MM (24-hour format)")


# ============== Response Schemas ==============

class TimeSlot(BaseModel):
    """Available time slots for a specific date."""

    date: str = Field(description="Date in YYYY-MM-DD format")
    times: list[str] = Field(description="Available times in HH:MM format")


class AvailabilityResponse(BaseModel):
    """Response for availability check."""

    available_slots: list[TimeSlot]
    timezone: str


class BookingResponse(BaseModel):
    """Response for successful booking creation."""

    success: bool = True
    booking_id: str
    confirmed_datetime: str = Field(description="ISO 8601 datetime with timezone")
    message: str


class BookingDetailResponse(BaseModel):
    """Detailed booking response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    appointment_datetime: datetime
    timezone: str
    first_name: str
    last_name: str
    email: str
    phone: str
    contact_id: UUID | None
    status: str
    created_at: datetime


class ErrorResponse(BaseModel):
    """Error response for voice agent."""

    success: bool = False
    error: str
    error_code: str | None = None
