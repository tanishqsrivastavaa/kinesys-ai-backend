"""
Comprehensive test suite for calendar endpoints.

Tests cover:
- Calendar status endpoint
- List events with filters
- Get single event
- Create event with lead linking
- Update event
- Delete event
- Events for lead
- Error handling
- Google Calendar API mocking
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from googleapiclient.errors import HttpError

from app.models.user_model import User
from app.models.calendar_event_link_model import CalendarEventLink
from app.schemas.calendar_schema import CalendarEventResponse


# ============== Calendar Status Tests ==============

@pytest.mark.asyncio
class TestCalendarStatus:
    """Tests for GET /api/v1/calendar/status endpoint."""

    async def test_status_not_connected(self, client: AsyncClient, test_user: User):
        """Test status when Google Calendar is not connected."""
        response = await client.get("/api/v1/calendar/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["email"] is None
        assert data["calendar_id"] is None

    async def test_status_connected(
        self,
        client_with_calendar_user: AsyncClient,
        test_user_with_calendar: User
    ):
        """Test status when Google Calendar is connected."""
        response = await client_with_calendar_user.get("/api/v1/calendar/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["email"] == test_user_with_calendar.email
        assert data["calendar_id"] == "primary"


# ============== List Events Tests ==============

@pytest.mark.asyncio
class TestListEvents:
    """Tests for GET /api/v1/calendar/events endpoint."""

    async def test_list_events_no_credentials(self, client: AsyncClient):
        """Test listing events without Google credentials."""
        response = await client.get("/api/v1/calendar/events")

        assert response.status_code == 401
        assert "not connected" in response.json()["detail"].lower()

    async def test_list_events_success(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test successful event listing."""
        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.get("/api/v1/calendar/events")

            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert isinstance(data["data"], list)

    async def test_list_events_with_time_range(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test listing events with time range filter."""
        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            now = datetime.now(ZoneInfo("UTC"))
            time_min = now.isoformat()
            time_max = (now + timedelta(days=7)).isoformat()

            response = await client_with_calendar_user.get(
                "/api/v1/calendar/events",
                params={"time_min": time_min, "time_max": time_max}
            )

            assert response.status_code == 200

    async def test_list_events_with_search(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test listing events with search query."""
        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.get(
                "/api/v1/calendar/events",
                params={"q": "meeting"}
            )

            assert response.status_code == 200

    async def test_list_events_pagination(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test event listing pagination."""
        mock_calendar_service.events().list().execute.return_value = {
            "items": [],
            "nextPageToken": "next_page_123",
        }

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.get(
                "/api/v1/calendar/events",
                params={"max_results": 10}
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("next_page_token") == "next_page_123"

    async def test_list_events_google_api_error(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test error handling for Google API errors."""
        # Mock HTTP error
        http_error = HttpError(
            resp=MagicMock(status=500),
            content=b"Internal Server Error"
        )
        http_error.reason = "Internal Server Error"
        mock_calendar_service.events().list().execute.side_effect = http_error

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.get("/api/v1/calendar/events")

            assert response.status_code == 500


# ============== Get Single Event Tests ==============

@pytest.mark.asyncio
class TestGetEvent:
    """Tests for GET /api/v1/calendar/events/{event_id} endpoint."""

    async def test_get_event_success(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test getting a single event."""
        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.get(
                "/api/v1/calendar/events/event_1"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "event_1"
            assert "title" in data
            assert "start_datetime" in data
            assert "end_datetime" in data

    async def test_get_event_not_found(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test getting non-existent event."""
        http_error = HttpError(
            resp=MagicMock(status=404),
            content=b"Not Found"
        )
        http_error.reason = "Not Found"
        mock_calendar_service.events().get().execute.side_effect = http_error

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.get(
                "/api/v1/calendar/events/nonexistent_event"
            )

            assert response.status_code == 404

    async def test_get_event_with_lead_link(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock,
        db_session: AsyncSession,
        test_user_with_calendar: User
    ):
        """Test getting event that has a lead link."""
        lead_id = uuid4()

        # Create event link
        event_link = CalendarEventLink(
            id=uuid4(),
            google_event_id="event_1",
            lead_id=lead_id,
            user_id=test_user_with_calendar.id,
            event_title="Test Event",
        )
        db_session.add(event_link)
        await db_session.commit()

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.get(
                "/api/v1/calendar/events/event_1"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["lead_id"] == str(lead_id)


# ============== Create Event Tests ==============

@pytest.mark.asyncio
class TestCreateEvent:
    """Tests for POST /api/v1/calendar/events endpoint."""

    async def test_create_event_success(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test successful event creation."""
        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            now = datetime.now(ZoneInfo("UTC"))
            start = (now + timedelta(days=1)).isoformat()
            end = (now + timedelta(days=1, hours=1)).isoformat()

            response = await client_with_calendar_user.post(
                "/api/v1/calendar/events",
                json={
                    "title": "New Meeting",
                    "start_datetime": start,
                    "end_datetime": end,
                    "timezone": "America/New_York",
                }
            )

            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["title"] == "New Meeting"

    async def test_create_event_with_all_fields(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test event creation with all optional fields."""
        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            now = datetime.now(ZoneInfo("UTC"))
            start = (now + timedelta(days=2)).isoformat()
            end = (now + timedelta(days=2, hours=2)).isoformat()

            response = await client_with_calendar_user.post(
                "/api/v1/calendar/events",
                json={
                    "title": "Full Meeting",
                    "description": "A detailed meeting description",
                    "start_datetime": start,
                    "end_datetime": end,
                    "timezone": "America/New_York",
                    "location": "Conference Room A",
                    "attendees": ["attendee1@example.com", "attendee2@example.com"],
                }
            )

            assert response.status_code == 201

    async def test_create_event_with_lead_link(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock,
        db_session: AsyncSession,
        test_user_with_calendar: User
    ):
        """Test event creation with lead link."""
        lead_id = uuid4()

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            now = datetime.now(ZoneInfo("UTC"))
            start = (now + timedelta(days=3)).isoformat()
            end = (now + timedelta(days=3, hours=1)).isoformat()

            response = await client_with_calendar_user.post(
                "/api/v1/calendar/events",
                json={
                    "title": "Lead Meeting",
                    "start_datetime": start,
                    "end_datetime": end,
                    "timezone": "America/New_York",
                    "lead_id": str(lead_id),
                }
            )

            assert response.status_code == 201
            data = response.json()
            assert data["lead_id"] == str(lead_id)

    async def test_create_event_missing_title(
        self,
        client_with_calendar_user: AsyncClient
    ):
        """Test validation error for missing title."""
        now = datetime.now(ZoneInfo("UTC"))
        start = (now + timedelta(days=1)).isoformat()
        end = (now + timedelta(days=1, hours=1)).isoformat()

        response = await client_with_calendar_user.post(
            "/api/v1/calendar/events",
            json={
                "start_datetime": start,
                "end_datetime": end,
                "timezone": "America/New_York",
            }
        )

        assert response.status_code == 422  # Validation error

    async def test_create_event_google_api_error(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test error handling for Google API errors during creation."""
        http_error = HttpError(
            resp=MagicMock(status=400),
            content=b"Bad Request"
        )
        http_error.reason = "Bad Request"
        mock_calendar_service.events().insert().execute.side_effect = http_error

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            now = datetime.now(ZoneInfo("UTC"))
            start = (now + timedelta(days=1)).isoformat()
            end = (now + timedelta(days=1, hours=1)).isoformat()

            response = await client_with_calendar_user.post(
                "/api/v1/calendar/events",
                json={
                    "title": "Test Event",
                    "start_datetime": start,
                    "end_datetime": end,
                    "timezone": "America/New_York",
                }
            )

            assert response.status_code == 400


# ============== Update Event Tests ==============

@pytest.mark.asyncio
class TestUpdateEvent:
    """Tests for PUT /api/v1/calendar/events/{event_id} endpoint."""

    async def test_update_event_success(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test successful event update."""
        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.put(
                "/api/v1/calendar/events/event_1",
                json={"title": "Updated Meeting Title"}
            )

            assert response.status_code == 200

    async def test_update_event_change_time(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test updating event time."""
        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            now = datetime.now(ZoneInfo("UTC"))
            new_start = (now + timedelta(days=5)).isoformat()
            new_end = (now + timedelta(days=5, hours=2)).isoformat()

            response = await client_with_calendar_user.put(
                "/api/v1/calendar/events/event_1",
                json={
                    "start_datetime": new_start,
                    "end_datetime": new_end,
                    "timezone": "America/New_York",
                }
            )

            assert response.status_code == 200

    async def test_update_event_not_found(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test updating non-existent event."""
        http_error = HttpError(
            resp=MagicMock(status=404),
            content=b"Not Found"
        )
        http_error.reason = "Not Found"
        mock_calendar_service.events().get().execute.side_effect = http_error

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.put(
                "/api/v1/calendar/events/nonexistent",
                json={"title": "Updated"}
            )

            assert response.status_code == 404

    async def test_update_event_add_lead_link(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock,
        db_session: AsyncSession
    ):
        """Test adding lead link to existing event."""
        lead_id = uuid4()

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.put(
                "/api/v1/calendar/events/event_1",
                json={"lead_id": str(lead_id)}
            )

            assert response.status_code == 200


# ============== Delete Event Tests ==============

@pytest.mark.asyncio
class TestDeleteEvent:
    """Tests for DELETE /api/v1/calendar/events/{event_id} endpoint."""

    async def test_delete_event_success(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test successful event deletion."""
        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.delete(
                "/api/v1/calendar/events/event_1"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    async def test_delete_event_with_send_updates(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test deletion with send_updates parameter."""
        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.delete(
                "/api/v1/calendar/events/event_1",
                params={"send_updates": False}
            )

            assert response.status_code == 200

    async def test_delete_event_removes_link(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock,
        db_session: AsyncSession,
        test_user_with_calendar: User
    ):
        """Test that deleting event removes the lead link."""
        # Create event link
        event_link = CalendarEventLink(
            id=uuid4(),
            google_event_id="event_to_delete",
            lead_id=uuid4(),
            user_id=test_user_with_calendar.id,
            event_title="Event to Delete",
        )
        db_session.add(event_link)
        await db_session.commit()

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.delete(
                "/api/v1/calendar/events/event_to_delete"
            )

            assert response.status_code == 200

    async def test_delete_already_deleted_event(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test deleting event that was already deleted from Google."""
        http_error = HttpError(
            resp=MagicMock(status=404),
            content=b"Not Found"
        )
        http_error.reason = "Not Found"
        mock_calendar_service.events().delete().execute.side_effect = http_error

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            # Should still succeed (clean up our link)
            response = await client_with_calendar_user.delete(
                "/api/v1/calendar/events/already_deleted"
            )

            assert response.status_code == 200


# ============== Events for Lead Tests ==============

@pytest.mark.asyncio
class TestEventsForLead:
    """Tests for GET /api/v1/calendar/lead/{lead_id}/events endpoint."""

    async def test_get_events_for_lead_success(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock,
        db_session: AsyncSession,
        test_user_with_calendar: User
    ):
        """Test getting events linked to a lead."""
        lead_id = uuid4()

        # Create event links
        for i in range(3):
            event_link = CalendarEventLink(
                id=uuid4(),
                google_event_id=f"lead_event_{i}",
                lead_id=lead_id,
                user_id=test_user_with_calendar.id,
                event_title=f"Lead Event {i}",
            )
            db_session.add(event_link)
        await db_session.commit()

        # Mock individual event fetch
        mock_calendar_service.events().get().execute.return_value = {
            "id": "lead_event_0",
            "summary": "Lead Event 0",
            "start": {"dateTime": "2026-01-27T10:00:00-05:00"},
            "end": {"dateTime": "2026-01-27T11:00:00-05:00"},
            "status": "confirmed",
        }

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.get(
                f"/api/v1/calendar/lead/{lead_id}/events"
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    async def test_get_events_for_lead_no_events(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock
    ):
        """Test getting events for lead with no linked events."""
        lead_id = uuid4()

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.get(
                f"/api/v1/calendar/lead/{lead_id}/events"
            )

            assert response.status_code == 200
            data = response.json()
            assert data == []

    async def test_get_events_for_lead_cleans_deleted_events(
        self,
        client_with_calendar_user: AsyncClient,
        mock_calendar_service: MagicMock,
        db_session: AsyncSession,
        test_user_with_calendar: User
    ):
        """Test that deleted Google events are cleaned up."""
        lead_id = uuid4()

        # Create event link for deleted event
        event_link = CalendarEventLink(
            id=uuid4(),
            google_event_id="deleted_event",
            lead_id=lead_id,
            user_id=test_user_with_calendar.id,
            event_title="Deleted Event",
        )
        db_session.add(event_link)
        await db_session.commit()

        # Mock 404 response
        http_error = HttpError(
            resp=MagicMock(status=404),
            content=b"Not Found"
        )
        http_error.reason = "Not Found"
        mock_calendar_service.events().get().execute.side_effect = http_error

        with patch(
            "app.api.v1.routers.calendar.get_calendar_service",
            return_value=mock_calendar_service
        ):
            response = await client_with_calendar_user.get(
                f"/api/v1/calendar/lead/{lead_id}/events"
            )

            assert response.status_code == 200
            # Event should be excluded (link cleaned up)
            assert response.json() == []


# ============== CalendarEventResponse Schema Tests ==============

class TestCalendarEventResponseSchema:
    """Unit tests for CalendarEventResponse schema."""

    def test_from_google_event_regular(self):
        """Test conversion of regular timed event."""
        google_event = {
            "id": "test_event",
            "summary": "Test Meeting",
            "description": "A test meeting",
            "start": {"dateTime": "2026-01-27T10:00:00-05:00", "timeZone": "America/New_York"},
            "end": {"dateTime": "2026-01-27T11:00:00-05:00", "timeZone": "America/New_York"},
            "status": "confirmed",
            "htmlLink": "https://calendar.google.com/event?id=test_event",
            "creator": {"email": "creator@example.com"},
            "organizer": {"email": "organizer@example.com"},
            "attendees": [
                {"email": "attendee@example.com", "responseStatus": "accepted"}
            ],
        }

        response = CalendarEventResponse.from_google_event(google_event)

        assert response.id == "test_event"
        assert response.title == "Test Meeting"
        assert response.description == "A test meeting"
        assert response.is_all_day is False
        assert len(response.attendees) == 1
        assert response.attendees[0].email == "attendee@example.com"

    def test_from_google_event_all_day(self):
        """Test conversion of all-day event."""
        google_event = {
            "id": "all_day_event",
            "summary": "All Day Event",
            "start": {"date": "2026-01-27"},
            "end": {"date": "2026-01-28"},
            "status": "confirmed",
        }

        response = CalendarEventResponse.from_google_event(google_event)

        assert response.id == "all_day_event"
        assert response.is_all_day is True
        assert response.start_date == "2026-01-27"
        assert response.end_date == "2026-01-28"

    def test_from_google_event_with_lead_id(self):
        """Test conversion with lead_id."""
        lead_id = uuid4()
        google_event = {
            "id": "linked_event",
            "summary": "Linked Event",
            "start": {"dateTime": "2026-01-27T10:00:00Z"},
            "end": {"dateTime": "2026-01-27T11:00:00Z"},
            "status": "confirmed",
        }

        response = CalendarEventResponse.from_google_event(google_event, lead_id)

        assert response.lead_id == lead_id

    def test_from_google_event_no_title(self):
        """Test conversion of event without summary."""
        google_event = {
            "id": "no_title_event",
            "start": {"dateTime": "2026-01-27T10:00:00Z"},
            "end": {"dateTime": "2026-01-27T11:00:00Z"},
            "status": "confirmed",
        }

        response = CalendarEventResponse.from_google_event(google_event)

        assert response.title == "No Title"
