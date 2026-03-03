# Kinesys Backend API

A high-performance, async FastAPI backend for the Kinesys CRM application. Provides RESTful APIs for lead management, Google Calendar integration, real-time communication via WebSockets, and AI-powered voice agent capabilities.

## Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Database](#database)
- [Authentication](#authentication)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Integrations](#integrations)
- [WebSocket API](#websocket-api)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

## Features

### Lead Management
- Full CRUD operations for leads with soft delete support
- Advanced filtering by status, stage, temperature, source, owner, and tags
- Pagination with configurable page size
- Lead scoring and temperature tracking
- Automatic stage history tracking
- Tag system with custom colors
- Kanban view data (leads grouped by stage)
- Custom fields via JSONB storage

### Authentication and Authorization
- Google OAuth 2.0 integration
- JWT-based authentication with access and refresh tokens
- Secure refresh token rotation with HttpOnly cookies
- CSRF protection for OAuth flow
- User profile management

### Calendar Integration
- Full Google Calendar API integration
- Create, read, update, and delete calendar events
- Link calendar events to CRM leads
- Automatic credential refresh
- Attendee management
- Event search and filtering

### Booking System
- Availability engine for appointment scheduling
- 7-day availability window with configurable business hours
- Timezone-aware scheduling (IANA format)
- Idempotent booking creation
- Voice agent-friendly response formatting

### Real-time Communication
- WebSocket support for live call streaming
- Agent-to-frontend message broadcasting
- Call-specific subscriptions
- Connection state management

### AI Voice Agent
- LiveKit integration for video/audio rooms
- Dynamic agent dispatch with configuration
- Participant token generation
- Room management

## Technology Stack

### Core Framework
- **FastAPI** - Modern, high-performance web framework
- **SQLModel** - SQL databases with Python type hints
- **SQLAlchemy** - Async ORM with PostgreSQL support
- **Pydantic** - Data validation and settings management

### Database
- **PostgreSQL** - Primary database (via asyncpg driver)
- **Alembic** - Database migration tool

### Authentication
- **PyJWT** - JSON Web Token implementation
- **google-auth-oauthlib** - Google OAuth 2.0 client
- **google-api-python-client** - Google APIs client
- **passlib** + **bcrypt** - Password hashing

### Real-time and Video
- **WebSockets** - Real-time bidirectional communication
- **LiveKit** - Video conferencing platform SDK
- **livekit-api** - LiveKit server-side API

### AI and ML
- **Pydantic AI** - AI agent framework

## Prerequisites

- Python 3.12 or higher
- PostgreSQL 14+ (or NeonDB for serverless)
- Google Cloud Console project with OAuth 2.0 credentials
- LiveKit server (optional, for voice agent features)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-org/kinesys-backend.git
cd kinesys-backend
```

2. Create and activate a virtual environment:
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Or using standard venv
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:
```bash
# Using uv
uv pip install -e .

# Or using pip
pip install -e .

# Install test dependencies (optional)
uv pip install -e ".[test]"
```

4. Create environment configuration:
```bash
cp .env.example .env
```

5. Configure environment variables (see [Configuration](#configuration))

6. Run database migrations:
```bash
cd backend
alembic upgrade head
```

7. Start the development server:
```bash
uvicorn app.main:app --reload --app-dir backend
```

The API will be available at `http://localhost:8000`.

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Project Configuration
PROJECT_NAME=Kinesys
MODE=development
SECRET_KEY=your-secret-key-min-32-characters

# Google OAuth 2.0
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback

# Database (PostgreSQL)
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=your-password
DATABASE_NAME=kinesys

# Optional: Override full database URI
# ASYNC_DATABASE_URI=postgresql+asyncpg://user:pass@host:port/db?ssl=require

# LiveKit (Optional - for voice agent)
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
LIVEKIT_AGENT_NAME=kinesys-agent

# OpenAI (Optional - for AI features)
OPENAI_API_KEY=sk-your-openai-key
```

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the following APIs:
   - Google Calendar API
   - Google People API (for user info)
4. Configure OAuth consent screen
5. Create OAuth 2.0 credentials (Web application type)
6. Add authorized redirect URIs:
   - Development: `http://localhost:8000/api/v1/auth/callback`
   - Production: `https://api.yourdomain.com/api/v1/auth/callback`
7. Copy Client ID and Client Secret to your `.env` file

### Database Setup

**Local PostgreSQL:**
```bash
createdb kinesys
```

**NeonDB (Serverless):**
1. Create a project at [neon.tech](https://neon.tech)
2. Copy the connection string to `ASYNC_DATABASE_URI`
3. Ensure `?ssl=require` is appended

## Running the Application

### Development Server

```bash
cd kinesys-backend
uvicorn app.main:app --reload --app-dir backend --port 8000
```

Options:
- `--reload` - Enable auto-reload on code changes
- `--port 8000` - Server port (default: 8000)
- `--host 0.0.0.0` - Bind to all interfaces

### Production Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or with Gunicorn:
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/api/v1/openapi.json

## Database

### Running Migrations

```bash
cd backend

# Generate a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

### Database Schema

The application uses the following main tables:

**users**
- User accounts with Google OAuth integration
- Stores Google credentials for Calendar API access
- JWT refresh token management

**leads**
- CRM lead records with comprehensive fields
- Soft delete support (is_active, deleted_at)
- JSONB fields for interests and custom_fields

**lead_stage_history**
- Audit trail of stage changes
- Tracks who changed, when, and optional notes

**tags** and **lead_tags**
- Tag system with many-to-many relationship
- Per-user tag namespace

**bookings**
- Appointment scheduling
- Unique constraint prevents double-booking

**calendar_event_links**
- Links Google Calendar events to CRM leads
- Caches event title and start time

## Authentication

### OAuth 2.0 Flow

1. **Initiate Login:**
   ```
   GET /api/v1/auth/login
   ```
   Redirects to Google consent screen.

2. **Handle Callback:**
   ```
   GET /api/v1/auth/callback?code=...&state=...
   ```
   Exchanges authorization code for tokens, creates/updates user, returns JWT.

3. **Access Protected Endpoints:**
   ```
   Authorization: Bearer <access_token>
   ```

4. **Refresh Token:**
   ```
   POST /api/v1/auth/refresh
   Cookie: refresh_token=<token>
   ```

### Token Details

| Token | Lifetime | Storage | Purpose |
|-------|----------|---------|---------|
| Access Token | 15 minutes | Client (localStorage) | API authentication |
| Refresh Token | 7 days | HttpOnly cookie | Token renewal |

### Google Scopes

The application requests the following OAuth scopes:
- `https://www.googleapis.com/auth/calendar.events` - Calendar event management
- `https://www.googleapis.com/auth/userinfo.email` - User email address
- `https://www.googleapis.com/auth/userinfo.profile` - User profile information

## Project Structure

```
kinesys-backend/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── routers/           # API route handlers
│   │   │       │   ├── auth.py        # Authentication endpoints
│   │   │       │   ├── leads.py       # Lead management
│   │   │       │   ├── bookings.py    # Appointment scheduling
│   │   │       │   ├── calls.py       # WebSocket call handling
│   │   │       │   ├── calendar.py    # Google Calendar integration
│   │   │       │   └── ai_calling.py  # LiveKit agent dispatch
│   │   │       ├── api.py             # Router aggregation
│   │   │       └── deps.py            # Dependency injection
│   │   ├── models/                    # SQLModel database models
│   │   │   ├── user_model.py
│   │   │   ├── lead_model.py
│   │   │   ├── booking_model.py
│   │   │   ├── calendar_event_link_model.py
│   │   │   ├── base_model.py          # Base classes and mixins
│   │   │   └── enums/                 # Enum definitions
│   │   ├── schemas/                   # Pydantic request/response schemas
│   │   │   ├── user_schema.py
│   │   │   ├── lead_schema.py
│   │   │   ├── booking_schema.py
│   │   │   └── calendar_schema.py
│   │   ├── crud/                      # Database operations
│   │   │   ├── user_crud.py
│   │   │   ├── lead_crud.py
│   │   │   ├── booking_crud.py
│   │   │   └── base_crud.py
│   │   ├── controllers/               # Business logic
│   │   │   └── auth.py                # OAuth flow handling
│   │   ├── services/                  # Service layer
│   │   │   ├── websocket_manager.py   # WebSocket connection management
│   │   │   └── agent_service.py       # AI agent service
│   │   ├── core/                      # Core configuration
│   │   │   ├── config.py              # Settings management
│   │   │   └── jwt.py                 # JWT utilities
│   │   ├── db/
│   │   │   └── database.py            # Database connection
│   │   ├── prompts/                   # AI agent prompts
│   │   ├── utils/                     # Utility functions
│   │   └── main.py                    # FastAPI application
│   ├── alembic/                       # Database migrations
│   │   ├── versions/                  # Migration files
│   │   └── env.py                     # Migration configuration
│   └── tests/                         # Test suite
├── pyproject.toml                     # Project dependencies
├── .env                               # Environment variables
└── README.md                          # This file
```

## API Endpoints

### Authentication (`/api/v1/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/login` | Redirect to Google OAuth |
| GET | `/callback` | Handle OAuth callback |
| GET | `/callback/json` | OAuth callback (JSON response) |
| POST | `/refresh` | Refresh access token |
| POST | `/logout` | Invalidate refresh token |
| GET | `/me` | Get current user profile |
| GET | `/users` | List all users |

### Leads (`/api/v1/leads`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List leads with filters |
| POST | `/` | Create new lead |
| GET | `/by-stage` | Get leads grouped by stage |
| GET | `/{lead_id}` | Get single lead |
| PUT | `/{lead_id}` | Update lead |
| DELETE | `/{lead_id}` | Soft delete lead |
| GET | `/tags` | List user's tags |
| POST | `/tags` | Create tag |
| DELETE | `/tags/{tag_id}` | Delete tag |
| GET | `/meta/stages` | List lead stages |
| GET | `/meta/statuses` | List lead statuses |
| GET | `/meta/sources` | List lead sources |
| GET | `/meta/temperatures` | List temperatures |
| GET | `/meta/industries` | List industries |
| GET | `/meta/territories` | List territories |
| GET | `/meta/employee-counts` | List employee ranges |
| GET | `/meta/all` | Get all metadata |

### Bookings (`/api/v1/bookings`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/availability` | Get available time slots |
| POST | `/create` | Create booking (idempotent) |

### Calendar (`/api/v1/calendar`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/events` | List calendar events |
| POST | `/events` | Create calendar event |
| GET | `/events/{event_id}` | Get single event |
| PUT | `/events/{event_id}` | Update event |
| DELETE | `/events/{event_id}` | Delete event |
| GET | `/status` | Check calendar connection |
| GET | `/lead/{lead_id}/events` | Get events for a lead |

### Calls (`/api/v1/calls`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/active` | List active calls |
| GET | `/{call_id}/status` | Get call connection status |

### AI Calling (`/api/v1/ai-calling`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/dispatch` | Dispatch AI agent to room |
| POST | `/token` | Generate LiveKit token |
| GET | `/rooms` | List active rooms |

## Integrations

### Google Calendar

The backend provides full Google Calendar integration:

1. **Authorization:** OAuth scopes include `calendar.events`
2. **Credential Storage:** Encrypted credentials stored in user record
3. **Auto-refresh:** Expired credentials are automatically refreshed
4. **Event Linking:** Events can be linked to CRM leads

Example: Create a calendar event linked to a lead:
```json
POST /api/v1/calendar/events
{
  "title": "Sales Call",
  "description": "Follow-up discussion",
  "start_datetime": "2024-01-15T10:00:00Z",
  "end_datetime": "2024-01-15T11:00:00Z",
  "lead_id": "uuid-of-lead",
  "attendees": ["client@example.com"]
}
```

### LiveKit Voice Agent

Configure AI voice agents for automated calls:

```json
POST /api/v1/ai-calling/dispatch
{
  "agent_config": {
    "system_prompt": "You are a helpful sales assistant...",
    "welcome_message": "Hello, this is Kinesys calling...",
    "ai_speaks_first": true,
    "voice_id": "voice-123",
    "llm_model": "gpt-4o-mini",
    "stt_model": "nova-3"
  },
  "room_name": "call-abc123"
}
```

## WebSocket API

### Agent Connection

```
WS /ws/agent
```

Agents send messages in the format:
```json
{
  "id": "call_id",
  "type": "transcript|event|status",
  "data": { ... }
}
```

### Frontend Subscription

```
WS /ws/calls/{call_id}
```

Frontends receive broadcasted messages from the agent. Supported commands:
- `ping` - Keep-alive (responds with `pong`)
- `status` - Get connection count

## Testing

### Install Test Dependencies

```bash
uv pip install -e ".[test]"
```

### Run Tests

```bash
cd backend
pytest

# With coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_leads.py

# Run with verbose output
pytest -v
```

### Test Configuration

Tests use SQLite in-memory database by default. Configure test database in `conftest.py` if needed.

## Deployment

### Docker

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
COPY backend/ backend/

RUN pip install uv && uv pip install --system -e .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
```

Build and run:
```bash
docker build -t kinesys-backend .
docker run -p 8000:8000 --env-file .env kinesys-backend
```

### Production Checklist

1. Set `MODE=production` in environment
2. Use strong `SECRET_KEY` (minimum 32 characters)
3. Configure proper database with SSL
4. Set up HTTPS with reverse proxy (nginx/Caddy)
5. Configure CORS for production domains
6. Set up database backups
7. Configure logging and monitoring
8. Use process manager (systemd/supervisor)

### CORS Configuration

Update `ALLOWED_ORIGINS` in `app/main.py` for production:

```python
ALLOWED_ORIGINS = [
    "https://yourdomain.com",
    "https://app.yourdomain.com",
]
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Make your changes following the code style
4. Write tests for new functionality
5. Run the test suite (`pytest`)
6. Commit your changes (`git commit -m 'Add new feature'`)
7. Push to the branch (`git push origin feature/new-feature`)
8. Open a Pull Request

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all functions
- Write docstrings for public functions
- Keep functions focused and single-purpose
- Use async/await for I/O operations

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

For frontend documentation, see the [Frontend README](../Kinesys/crm/README.md).
