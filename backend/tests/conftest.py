"""
Pytest configuration and fixtures for testing.
"""

import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

# Import only models that work with SQLite (no JSONB)
from app.models.user_model import User
from app.models.booking_model import Booking, BookingStatus
from app.models.calendar_event_link_model import CalendarEventLink


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with only the routes we need."""
    from fastapi import FastAPI
    from starlette.middleware.cors import CORSMiddleware

    app = FastAPI(title="Test App")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import routers
    from app.api.v1.routers import bookings, calendar

    # Create API router
    from fastapi import APIRouter
    api_router = APIRouter()
    api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
    api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])

    app.include_router(api_router, prefix="/api/v1")

    return app


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async engine for testing."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Create only the tables we need using raw SQL (avoids JSONB issues)
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    google_id TEXT UNIQUE NOT NULL,
                    full_name TEXT,
                    picture_url TEXT,
                    google_credentials_json TEXT,
                    refresh_token TEXT,
                    refresh_token_expires TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
        )
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id TEXT PRIMARY KEY,
                    appointment_datetime TIMESTAMP NOT NULL,
                    timezone TEXT NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    contact_id TEXT,
                    status TEXT DEFAULT 'confirmed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    deleted_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
        )
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS calendar_event_links (
                    id TEXT PRIMARY KEY,
                    google_event_id TEXT NOT NULL,
                    lead_id TEXT,
                    user_id TEXT NOT NULL,
                    event_title TEXT,
                    event_start TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
        )

    yield engine

    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS calendar_event_links"))
        await conn.execute(text("DROP TABLE IF EXISTS bookings"))
        await conn.execute(text("DROP TABLE IF EXISTS users"))
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test."""
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with async_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        google_id="test_google_id_123",
        google_credentials_json=None,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_with_calendar(db_session: AsyncSession) -> User:
    """Create a test user with Google Calendar credentials."""
    import json
    creds = {
        "token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
        "scopes": ["https://www.googleapis.com/auth/calendar"],
        "expiry": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
    }
    user = User(
        id=uuid4(),
        email="calendar@example.com",
        username="calendaruser",
        full_name="Calendar User",
        google_id="calendar_google_id_123",
        google_credentials_json=json.dumps(creds),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_booking(db_session: AsyncSession) -> Booking:
    """Create a test booking."""
    from zoneinfo import ZoneInfo
    booking = Booking(
        id=uuid4(),
        appointment_datetime=datetime.now(ZoneInfo("UTC")) + timedelta(days=1, hours=2),
        timezone="America/New_York",
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        status=BookingStatus.CONFIRMED.value,
    )
    db_session.add(booking)
    await db_session.commit()
    await db_session.refresh(booking)
    return booking


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with dependency overrides."""
    from app.api.deps import get_db, get_current_user

    app = create_test_app()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_with_calendar_user(
    db_session: AsyncSession,
    test_user_with_calendar: User
) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with a user that has calendar credentials."""
    from app.api.deps import get_db, get_current_user

    app = create_test_app()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user_with_calendar

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauthenticated_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client without authentication overrides."""
    from app.api.deps import get_db

    app = create_test_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# Mock Google Calendar Service
@pytest.fixture
def mock_calendar_service():
    """Create a mock Google Calendar service."""
    service = MagicMock()

    # Mock events().list()
    events_mock = MagicMock()
    events_mock.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "event_1",
                "summary": "Test Event 1",
                "start": {"dateTime": "2026-01-27T10:00:00-05:00"},
                "end": {"dateTime": "2026-01-27T11:00:00-05:00"},
                "status": "confirmed",
            },
            {
                "id": "event_2",
                "summary": "Test Event 2",
                "start": {"dateTime": "2026-01-28T14:00:00-05:00"},
                "end": {"dateTime": "2026-01-28T15:00:00-05:00"},
                "status": "confirmed",
            },
        ],
        "nextPageToken": None,
    }

    # Mock events().get()
    events_mock.get.return_value.execute.return_value = {
        "id": "event_1",
        "summary": "Test Event 1",
        "description": "Test description",
        "start": {"dateTime": "2026-01-27T10:00:00-05:00", "timeZone": "America/New_York"},
        "end": {"dateTime": "2026-01-27T11:00:00-05:00", "timeZone": "America/New_York"},
        "status": "confirmed",
        "htmlLink": "https://calendar.google.com/event?id=event_1",
    }

    # Mock events().insert()
    events_mock.insert.return_value.execute.return_value = {
        "id": "new_event_123",
        "summary": "New Meeting",
        "start": {"dateTime": "2026-01-29T09:00:00-05:00", "timeZone": "America/New_York"},
        "end": {"dateTime": "2026-01-29T10:00:00-05:00", "timeZone": "America/New_York"},
        "status": "confirmed",
        "htmlLink": "https://calendar.google.com/event?id=new_event_123",
    }

    # Mock events().update()
    events_mock.update.return_value.execute.return_value = {
        "id": "event_1",
        "summary": "Updated Event",
        "start": {"dateTime": "2026-01-27T11:00:00-05:00", "timeZone": "America/New_York"},
        "end": {"dateTime": "2026-01-27T12:00:00-05:00", "timeZone": "America/New_York"},
        "status": "confirmed",
    }

    # Mock events().delete()
    events_mock.delete.return_value.execute.return_value = None

    service.events.return_value = events_mock

    return service
