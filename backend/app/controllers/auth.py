"""
Google OAuth Authentication Controller

Handles the business logic for Google OAuth authentication flow.
"""
from datetime import datetime, timezone
from google_auth_oauthlib.flow import Flow
from sqlmodel.ext.asyncio.session import AsyncSession
import json

from app.core.config import settings
from app.core.jwt import create_access_token, create_refresh_token, decode_refresh_token
from app.crud.user_crud import user_crud
from app.schemas.user_schema import UserCreate
from app.models.user_model import User

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def get_google_flow() -> Flow:
    """Create Google OAuth flow with configured credentials."""
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )


def get_authorization_url(state: str) -> str:
    """Generate Google OAuth authorization URL."""
    flow = get_google_flow()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    return authorization_url


async def handle_oauth_callback(code: str, db: AsyncSession) -> dict:
    """
    Handle the OAuth callback from Google.
    
    1. Exchange code for tokens
    2. Get user info from Google
    3. Create or find user in database
    4. Store Google credentials
    5. Generate JWT token
    
    Returns dict with access_token and user info.
    """
    flow = get_google_flow()
    
    # Exchange authorization code for tokens
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    # Get user info from Google
    session = flow.authorized_session()
    userinfo = session.get("https://www.googleapis.com/oauth2/v3/userinfo").json()
    
    google_id = userinfo["sub"]
    email = userinfo["email"]
    name = userinfo.get("name", "")
    picture = userinfo.get("picture", "")
    
    # Find or create user
    user = await user_crud.get_by_google_id_or_email(db, google_id=google_id, email=email)
    
    if not user:
        user = await user_crud.create(
            db,
            obj_in=UserCreate(
                email=email,
                google_id=google_id,
                username=email.split("@")[0],
                full_name=name,
                picture_url=picture,
            ),
        )
    
    # Store Google credentials for Calendar API
    creds_json = json.dumps({
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else SCOPES,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    })
    await user_crud.update_google_credentials(db, user=user, credentials_json=creds_json)

    # Create JWT access token and refresh token
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token, refresh_expires = create_refresh_token({"sub": str(user.id)})

    # Store refresh token in database
    await user_crud.update_refresh_token(db, user=user, refresh_token=refresh_token, expires=refresh_expires)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "picture_url": user.picture_url,
        },
    }


async def refresh_access_token(refresh_token: str, db: AsyncSession) -> dict | None:
    """
    Refresh the access token using a valid refresh token.

    Implements rotating refresh tokens:
    - Validates the provided refresh token
    - Issues a new access token
    - Issues a new refresh token (rotation)
    - Invalidates the old refresh token

    Returns dict with new tokens, or None if refresh token is invalid.
    """
    # Decode and validate the refresh token
    payload = decode_refresh_token(refresh_token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    # Get user and verify the refresh token matches what's stored
    user = await user_crud.get_by_id(db, user_id)
    if not user:
        return None

    # Verify the token matches what's in the database (prevents reuse of old tokens)
    if user.refresh_token != refresh_token:
        # Token doesn't match - possibly reused old token (potential token theft)
        # Invalidate all refresh tokens for this user as a security measure
        await user_crud.update_refresh_token(db, user=user, refresh_token=None, expires=None)
        return None

    # Check if refresh token is expired in database
    if user.refresh_token_expires and user.refresh_token_expires < datetime.now(timezone.utc):
        # Token expired - clear it
        await user_crud.update_refresh_token(db, user=user, refresh_token=None, expires=None)
        return None

    # Generate new tokens (rotation)
    new_access_token = create_access_token({"sub": str(user.id)})
    new_refresh_token, refresh_expires = create_refresh_token({"sub": str(user.id)})

    # Store new refresh token (invalidates the old one)
    await user_crud.update_refresh_token(db, user=user, refresh_token=new_refresh_token, expires=refresh_expires)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


async def logout_user(user: User, db: AsyncSession) -> None:
    """Logout user by invalidating their refresh token."""
    await user_crud.update_refresh_token(db, user=user, refresh_token=None, expires=None)
