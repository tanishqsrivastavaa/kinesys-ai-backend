"""FastAPI router for Google Calendar integration."""

from datetime import datetime, timezone
from uuid import UUID
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user_model import User
from app.models.calendar_event_link_model import CalendarEventLink
from app.crud.user_crud import user_crud
from app.schemas.calendar_schema import (
    CalendarEventCreate,
    CalendarEventUpdate,
    CalendarEventResponse,
    CalendarEventsListResponse,
    CalendarStatusResponse,
)

router = APIRouter()


async def get_calendar_service(user: User, db: AsyncSession):
    """Build Google Calendar service from stored credentials."""
    if not user.google_credentials_json:
        raise HTTPException(401, "Google Calendar not connected. Please re-authenticate.")

    creds_dict = json.loads(user.google_credentials_json)

    # Handle expiry parsing
    expiry = None
    if creds_dict.get("expiry"):
        try:
            expiry = datetime.fromisoformat(creds_dict["expiry"])
        except ValueError:
            pass

    creds = Credentials(
        token=creds_dict["token"],
        refresh_token=creds_dict.get("refresh_token"),
        token_uri=creds_dict["token_uri"],
        client_id=creds_dict["client_id"],
        client_secret=creds_dict["client_secret"],
        scopes=creds_dict["scopes"],
        expiry=expiry,
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())
            # Update stored credentials
            new_creds_json = json.dumps({
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes) if creds.scopes else creds_dict["scopes"],
                "expiry": creds.expiry.isoformat() if creds.expiry else None,
            })
            await user_crud.update_google_credentials(db, user=user, credentials_json=new_creds_json)
        except Exception as e:
            raise HTTPException(401, f"Failed to refresh Google credentials: {str(e)}")

    return build("calendar", "v3", credentials=creds)


async def get_event_lead_id(db: AsyncSession, user_id: UUID, google_event_id: str) -> UUID | None:
    """Get the lead_id linked to a Google Calendar event."""
    result = await db.exec(
        select(CalendarEventLink)
        .where(CalendarEventLink.user_id == user_id)
        .where(CalendarEventLink.google_event_id == google_event_id)
    )
    link = result.first()
    return link.lead_id if link else None


async def save_event_link(
    db: AsyncSession,
    user_id: UUID,
    google_event_id: str,
    lead_id: UUID | None,
    event_title: str | None = None,
    event_start: datetime | None = None,
) -> CalendarEventLink:
    """Save or update the link between a Google event and a CRM lead."""
    # Check if link already exists
    result = await db.exec(
        select(CalendarEventLink)
        .where(CalendarEventLink.user_id == user_id)
        .where(CalendarEventLink.google_event_id == google_event_id)
    )
    existing = result.first()

    if existing:
        existing.lead_id = lead_id
        existing.event_title = event_title
        existing.event_start = event_start
        existing.updated_at = datetime.utcnow()
        db.add(existing)
    else:
        new_link = CalendarEventLink(
            user_id=user_id,
            google_event_id=google_event_id,
            lead_id=lead_id,
            event_title=event_title,
            event_start=event_start,
        )
        db.add(new_link)

    await db.commit()
    return existing if existing else new_link


async def delete_event_link(db: AsyncSession, user_id: UUID, google_event_id: str):
    """Delete the link between a Google event and a CRM lead."""
    result = await db.exec(
        select(CalendarEventLink)
        .where(CalendarEventLink.user_id == user_id)
        .where(CalendarEventLink.google_event_id == google_event_id)
    )
    link = result.first()
    if link:
        await db.delete(link)
        await db.commit()


# ============== GET Events ==============

@router.get("/events", response_model=CalendarEventsListResponse)
async def list_events(
    time_min: datetime | None = Query(default=None, description="Start of time range (ISO format)"),
    time_max: datetime | None = Query(default=None, description="End of time range (ISO format)"),
    q: str | None = Query(default=None, description="Search query"),
    max_results: int = Query(default=50, ge=1, le=250, description="Maximum events to return"),
    page_token: str | None = Query(default=None, description="Page token for pagination"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List calendar events with optional filters.

    - time_min: Only return events starting after this time
    - time_max: Only return events starting before this time
    - q: Search text in event title/description
    - max_results: Max events per page (default 50)
    - page_token: Token for fetching next page
    """
    service = await get_calendar_service(current_user, db)

    # Default to events from now onwards
    if not time_min:
        time_min = datetime.now(timezone.utc)

    params = {
        "calendarId": "primary",
        "timeMin": time_min.isoformat(),
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }

    if time_max:
        params["timeMax"] = time_max.isoformat()
    if q:
        params["q"] = q
    if page_token:
        params["pageToken"] = page_token

    try:
        events_result = service.events().list(**params).execute()
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=f"Google Calendar error: {e.reason}")

    google_events = events_result.get("items", [])

    # Convert to our schema and include lead links
    events = []
    for event in google_events:
        lead_id = await get_event_lead_id(db, current_user.id, event.get("id", ""))
        events.append(CalendarEventResponse.from_google_event(event, lead_id))

    return CalendarEventsListResponse(
        data=events,
        next_page_token=events_result.get("nextPageToken"),
        next_sync_token=events_result.get("nextSyncToken"),
    )


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single calendar event by ID."""
    service = await get_calendar_service(current_user, db)

    try:
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(404, "Event not found")
        raise HTTPException(status_code=e.resp.status, detail=f"Google Calendar error: {e.reason}")

    lead_id = await get_event_lead_id(db, current_user.id, event_id)
    return CalendarEventResponse.from_google_event(event, lead_id)


# ============== CREATE Event ==============

@router.post("/events", response_model=CalendarEventResponse, status_code=201)
async def create_event(
    event_in: CalendarEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new calendar event in the user's Google Calendar.

    The event will be created in the user's primary calendar.
    If a lead_id is provided, the event will be linked to that CRM lead.
    """
    service = await get_calendar_service(current_user, db)

    # Build Google Calendar event body
    event_body = {
        "summary": event_in.title,
        "start": {
            "dateTime": event_in.start_datetime.isoformat(),
            "timeZone": event_in.timezone,
        },
        "end": {
            "dateTime": event_in.end_datetime.isoformat(),
            "timeZone": event_in.timezone,
        },
    }

    if event_in.description:
        event_body["description"] = event_in.description

    if event_in.location:
        event_body["location"] = event_in.location

    if event_in.attendees:
        event_body["attendees"] = [{"email": email} for email in event_in.attendees]

    try:
        created_event = service.events().insert(
            calendarId="primary",
            body=event_body,
            sendUpdates="all" if event_in.attendees else "none",
        ).execute()
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=f"Failed to create event: {e.reason}")

    # Save link to CRM lead if provided
    if event_in.lead_id:
        await save_event_link(
            db,
            user_id=current_user.id,
            google_event_id=created_event["id"],
            lead_id=event_in.lead_id,
            event_title=event_in.title,
            event_start=event_in.start_datetime,
        )

    return CalendarEventResponse.from_google_event(created_event, event_in.lead_id)


# ============== UPDATE Event ==============

@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: str,
    event_in: CalendarEventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing calendar event.

    Only provided fields will be updated.
    """
    service = await get_calendar_service(current_user, db)

    # First get the existing event
    try:
        existing_event = service.events().get(calendarId="primary", eventId=event_id).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(404, "Event not found")
        raise HTTPException(status_code=e.resp.status, detail=f"Google Calendar error: {e.reason}")

    # Build update body with only provided fields
    if event_in.title is not None:
        existing_event["summary"] = event_in.title

    if event_in.description is not None:
        existing_event["description"] = event_in.description

    if event_in.location is not None:
        existing_event["location"] = event_in.location

    tz = event_in.timezone or existing_event.get("start", {}).get("timeZone", "UTC")

    if event_in.start_datetime is not None:
        existing_event["start"] = {
            "dateTime": event_in.start_datetime.isoformat(),
            "timeZone": tz,
        }

    if event_in.end_datetime is not None:
        existing_event["end"] = {
            "dateTime": event_in.end_datetime.isoformat(),
            "timeZone": tz,
        }

    if event_in.attendees is not None:
        existing_event["attendees"] = [{"email": email} for email in event_in.attendees]

    try:
        updated_event = service.events().update(
            calendarId="primary",
            eventId=event_id,
            body=existing_event,
            sendUpdates="all" if event_in.attendees else "none",
        ).execute()
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=f"Failed to update event: {e.reason}")

    # Update lead link if lead_id is provided
    lead_id = event_in.lead_id
    if lead_id is None:
        # Keep existing link
        lead_id = await get_event_lead_id(db, current_user.id, event_id)
    else:
        # Update link
        await save_event_link(
            db,
            user_id=current_user.id,
            google_event_id=event_id,
            lead_id=lead_id,
            event_title=event_in.title or existing_event.get("summary"),
            event_start=event_in.start_datetime,
        )

    return CalendarEventResponse.from_google_event(updated_event, lead_id)


# ============== DELETE Event ==============

@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    send_updates: bool = Query(default=True, description="Send cancellation emails to attendees"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a calendar event.

    This will remove the event from Google Calendar and any CRM lead link.
    """
    service = await get_calendar_service(current_user, db)

    try:
        service.events().delete(
            calendarId="primary",
            eventId=event_id,
            sendUpdates="all" if send_updates else "none",
        ).execute()
    except HttpError as e:
        if e.resp.status == 404:
            # Event already deleted, still remove our link
            pass
        else:
            raise HTTPException(status_code=e.resp.status, detail=f"Failed to delete event: {e.reason}")

    # Remove the lead link
    await delete_event_link(db, current_user.id, event_id)

    return {"success": True, "message": "Event deleted"}


# ============== Status Endpoint ==============

@router.get("/status", response_model=CalendarStatusResponse)
async def calendar_status(current_user: User = Depends(get_current_user)):
    """Check if user has Google Calendar connected."""
    connected = current_user.google_credentials_json is not None
    return CalendarStatusResponse(
        connected=connected,
        email=current_user.email if connected else None,
        calendar_id="primary" if connected else None,
    )


# ============== Events for Lead ==============

@router.get("/lead/{lead_id}/events", response_model=list[CalendarEventResponse])
async def get_events_for_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all calendar events linked to a specific CRM lead."""
    service = await get_calendar_service(current_user, db)

    # Get all event links for this lead
    result = await db.exec(
        select(CalendarEventLink)
        .where(CalendarEventLink.user_id == current_user.id)
        .where(CalendarEventLink.lead_id == lead_id)
    )
    links = result.all()

    events = []
    for link in links:
        try:
            event = service.events().get(
                calendarId="primary",
                eventId=link.google_event_id,
            ).execute()
            events.append(CalendarEventResponse.from_google_event(event, lead_id))
        except HttpError as e:
            # Event was deleted from Google Calendar, clean up our link
            if e.resp.status == 404:
                await db.delete(link)
                await db.commit()
            # Skip this event

    return events
