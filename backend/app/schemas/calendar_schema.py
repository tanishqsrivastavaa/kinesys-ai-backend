"""Calendar event schemas for request/response validation."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


class CalendarEventCreate(BaseModel):
    """Schema for creating a calendar event."""

    title: str = Field(max_length=255, description="Event title/summary")
    description: str | None = Field(default=None, description="Event description")
    start_datetime: datetime = Field(description="Start time in ISO format")
    end_datetime: datetime = Field(description="End time in ISO format")
    attendees: list[EmailStr] = Field(default_factory=list, description="List of attendee emails")
    location: str | None = Field(default=None, max_length=500, description="Event location")
    lead_id: UUID | None = Field(default=None, description="Link to CRM lead")
    timezone: str = Field(default="UTC", description="Timezone for the event")


class CalendarEventUpdate(BaseModel):
    """Schema for updating a calendar event."""

    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    attendees: list[EmailStr] | None = None
    location: str | None = Field(default=None, max_length=500)
    lead_id: UUID | None = None
    timezone: str | None = None


class CalendarAttendee(BaseModel):
    """Schema for event attendee."""

    email: str
    display_name: str | None = None
    response_status: str | None = None  # needsAction, declined, tentative, accepted
    organizer: bool = False
    self: bool = False


class CalendarEventResponse(BaseModel):
    """Schema for calendar event response."""

    id: str  # Google event ID
    title: str
    description: str | None = None
    start_datetime: datetime
    end_datetime: datetime
    start_date: str | None = None  # For all-day events
    end_date: str | None = None  # For all-day events
    is_all_day: bool = False
    attendees: list[CalendarAttendee] = Field(default_factory=list)
    location: str | None = None
    html_link: str | None = None  # Link to Google Calendar
    status: str = "confirmed"  # confirmed, tentative, cancelled
    creator_email: str | None = None
    organizer_email: str | None = None
    lead_id: UUID | None = None
    created: datetime | None = None
    updated: datetime | None = None

    @classmethod
    def from_google_event(cls, event: dict, lead_id: UUID | None = None) -> "CalendarEventResponse":
        """Convert Google Calendar API event to our schema."""
        # Handle dateTime vs date (all-day events)
        start = event.get("start", {})
        end = event.get("end", {})

        is_all_day = "date" in start and "dateTime" not in start

        if is_all_day:
            start_datetime = datetime.fromisoformat(start["date"])
            end_datetime = datetime.fromisoformat(end["date"])
        else:
            start_datetime = datetime.fromisoformat(start.get("dateTime", "").replace("Z", "+00:00"))
            end_datetime = datetime.fromisoformat(end.get("dateTime", "").replace("Z", "+00:00"))

        # Parse attendees
        attendees = []
        for att in event.get("attendees", []):
            attendees.append(CalendarAttendee(
                email=att.get("email", ""),
                display_name=att.get("displayName"),
                response_status=att.get("responseStatus"),
                organizer=att.get("organizer", False),
                self=att.get("self", False),
            ))

        # Parse timestamps
        created = None
        if event.get("created"):
            try:
                created = datetime.fromisoformat(event["created"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        updated = None
        if event.get("updated"):
            try:
                updated = datetime.fromisoformat(event["updated"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return cls(
            id=event.get("id", ""),
            title=event.get("summary", "No Title"),
            description=event.get("description"),
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            start_date=start.get("date") if is_all_day else None,
            end_date=end.get("date") if is_all_day else None,
            is_all_day=is_all_day,
            attendees=attendees,
            location=event.get("location"),
            html_link=event.get("htmlLink"),
            status=event.get("status", "confirmed"),
            creator_email=event.get("creator", {}).get("email"),
            organizer_email=event.get("organizer", {}).get("email"),
            lead_id=lead_id,
            created=created,
            updated=updated,
        )


class CalendarEventsListResponse(BaseModel):
    """Response for listing calendar events."""

    data: list[CalendarEventResponse]
    next_page_token: str | None = None
    next_sync_token: str | None = None


class CalendarStatusResponse(BaseModel):
    """Response for calendar connection status."""

    connected: bool
    email: str | None = None
    calendar_id: str | None = None
