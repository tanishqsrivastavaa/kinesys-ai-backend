from urllib.parse import urlencode

from fastapi import APIRouter, Request, HTTPException, Depends, Query, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession
import secrets

from app.core.config import settings
from app.core.jwt import REFRESH_TOKEN_EXPIRE_DAYS
from app.api.deps import get_db, get_current_user
from app.controllers.auth import get_authorization_url, handle_oauth_callback, refresh_access_token, logout_user
from app.crud.user_crud import user_crud
from app.schemas.user_schema import UserRead, UserListItem, UserListResponse
from app.models.user_model import User

router = APIRouter()

# Frontend callback URL - where to redirect after OAuth
FRONTEND_CALLBACK_URL = "http://localhost:5173/auth/callback"

# Cookie settings
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # Convert days to seconds


@router.get("/login")
async def login_google():
    """Redirect user to Google OAuth consent screen."""
    state = secrets.token_urlsafe(32)
    authorization_url = get_authorization_url(state)

    response = RedirectResponse(authorization_url)
    # For development, use less restrictive cookie settings
    # In production, use secure=True and samesite="lax"
    is_production = settings.MODE.value == "production"
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=is_production,
        samesite="lax" if is_production else "none",
        max_age=600,
    )
    return response


@router.get("/callback")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback, create/update user, redirect to frontend with JWT."""
    # Validate CSRF state (skip in development - localhost cookies don't work with cross-site redirects)
    is_production = settings.MODE.value == "production"
    if is_production:
        cookie_state = request.cookies.get("oauth_state")
        if not cookie_state or state != cookie_state:
            # Redirect to frontend with error
            error_params = urlencode({"error": "csrf", "error_description": "Invalid state - possible CSRF"})
            return RedirectResponse(f"{FRONTEND_CALLBACK_URL}?{error_params}")

    try:
        result = await handle_oauth_callback(code=code, db=db)
    except Exception as e:
        # Redirect to frontend with error
        error_params = urlencode({"error": "oauth_failed", "error_description": str(e)})
        response = RedirectResponse(f"{FRONTEND_CALLBACK_URL}?{error_params}")
        response.delete_cookie("oauth_state")
        return response

    # Redirect to frontend with access token in URL
    params = urlencode({"token": result["access_token"]})
    response = RedirectResponse(f"{FRONTEND_CALLBACK_URL}?{params}")
    response.delete_cookie("oauth_state")

    # Set refresh token as HttpOnly cookie (more secure than localStorage)
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=result["refresh_token"],
        httponly=True,
        secure=is_production,
        samesite="lax" if is_production else "lax",
        max_age=REFRESH_TOKEN_MAX_AGE,
        path="/api/v1/auth",  # Only send cookie to auth endpoints
    )
    return response


@router.get("/callback/json")
async def google_callback_json(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback, return JWT as JSON (for API clients)."""
    is_production = settings.MODE.value == "production"
    if is_production:
        cookie_state = request.cookies.get("oauth_state")
        if not cookie_state or state != cookie_state:
            raise HTTPException(400, "Invalid state - possible CSRF")

    try:
        result = await handle_oauth_callback(code=code, db=db)
    except Exception as e:
        raise HTTPException(400, f"OAuth failed: {e}")

    # Return tokens as JSON (refresh token also in HttpOnly cookie for browser clients)
    response = JSONResponse({
        "access_token": result["access_token"],
        "token_type": result["token_type"],
        "user": result["user"],
    })
    response.delete_cookie("oauth_state")

    # Also set refresh token as HttpOnly cookie
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=result["refresh_token"],
        httponly=True,
        secure=is_production,
        samesite="lax" if is_production else "lax",
        max_age=REFRESH_TOKEN_MAX_AGE,
        path="/api/v1/auth",
    )
    return response


@router.post("/refresh")
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
):
    """
    Refresh the access token using the refresh token from HttpOnly cookie.

    Returns a new access token and rotates the refresh token.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Refresh token not found. Please log in again.",
        )

    result = await refresh_access_token(refresh_token, db)

    if not result:
        # Clear the invalid refresh token cookie
        response = JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired refresh token. Please log in again."},
        )
        response.delete_cookie(
            key=REFRESH_TOKEN_COOKIE_NAME,
            path="/api/v1/auth",
        )
        return response

    is_production = settings.MODE.value == "production"

    # Return new access token
    response = JSONResponse({
        "access_token": result["access_token"],
        "token_type": result["token_type"],
    })

    # Set new refresh token cookie (rotation)
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=result["refresh_token"],
        httponly=True,
        secure=is_production,
        samesite="lax" if is_production else "lax",
        max_age=REFRESH_TOKEN_MAX_AGE,
        path="/api/v1/auth",
    )

    return response


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout user - invalidate refresh token."""
    await logout_user(current_user, db)

    response = JSONResponse({"message": "Successfully logged out"})
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path="/api/v1/auth",
    )
    return response


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return UserRead(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        picture_url=current_user.picture_url,
        has_google_calendar=current_user.google_credentials_json is not None,
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: str | None = Query(default=None, description="Search by name or email"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    """
    Get list of users for dropdowns (assignee selection).
    Returns all users in the system.
    """
    users, total_count = await user_crud.get_multi(
        db,
        skip=(page - 1) * page_size,
        limit=page_size,
    )

    # Filter by search if provided
    if search:
        search_lower = search.lower()
        users = [
            u for u in users
            if search_lower in (u.full_name or "").lower()
            or search_lower in u.email.lower()
            or search_lower in u.username.lower()
        ]

    return UserListResponse(
        data=[
            UserListItem(
                id=u.id,
                name=u.full_name or u.username,
                email=u.email,
                avatar=u.picture_url,
            )
            for u in users
        ],
        total_count=total_count,
    )