"""FastAPI router for Booking endpoints (Voice Agent)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.crud import booking_crud
from app.schemas.booking_schema import (
    AvailabilityResponse,
    BookingCreate,
    BookingResponse,
    ErrorResponse,
    TimeSlot,
)

router = APIRouter()


def validate_timezone(tz: str) -> ZoneInfo:
    """Validate and return ZoneInfo object."""
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": f"Invalid timezone: {tz}. Please use a valid IANA timezone like 'America/New_York' or 'Europe/London'.",
                "error_code": "INVALID_TIMEZONE",
            },
        )


def format_friendly_datetime(dt: datetime, tz: ZoneInfo) -> str:
    """Format datetime in a voice-friendly way."""
    local_dt = dt.astimezone(tz)
    # e.g., "January 25, 2026 at 9:00 AM EST"
    # Use %I and strip leading zero manually for cross-platform compatibility
    hour = local_dt.strftime("%I").lstrip("0")
    return local_dt.strftime(f"%B %d, %Y at {hour}:%M %p %Z")


@router.get(
    "/availability",
    response_model=AvailabilityResponse,
    responses={400: {"model": ErrorResponse}},
)
async def get_availability(
    timeZone: str = Query(
        description="IANA timezone identifier (e.g., 'America/New_York')",
        examples=["America/New_York", "Europe/London", "Asia/Tokyo"],
    ),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityResponse:
    """
    Get available booking slots for the next 7 days.

    Returns available time slots in the specified timezone.
    Excludes weekends and already-booked slots.

    **For Voice Agent**: Use this to offer available times to the caller.
    """
    # Validate timezone
    tz = validate_timezone(timeZone)
    utc = ZoneInfo("UTC")

    # Calculate date range (next 7 days)
    now = datetime.now(utc)
    start_date = now
    end_date = now + timedelta(days=8)  # Extra day for timezone edge cases

    # Get booked slots from database
    booked_slots = await booking_crud.get_booked_slots(db, start_date, end_date)

    # Generate available slots (9 AM to 8 PM working hours)
    available = booking_crud.generate_available_slots(
        booked_slots_utc=booked_slots,
        timezone_str=timeZone,
        days=7,
        start_hour=9,
        end_hour=20,  # 8 PM
        slot_duration_minutes=60,
    )

    # Convert to response format
    slots = [
        TimeSlot(date=date_str, times=times)
        for date_str, times in sorted(available.items())
    ]

    return AvailabilityResponse(
        available_slots=slots,
        timezone=timeZone,
    )


@router.post(
    "/create",
    response_model=BookingResponse,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def create_booking(
    booking_in: BookingCreate,
    db: AsyncSession = Depends(get_db),
) -> BookingResponse:
    """
    Create a new booking appointment.

    **Idempotent**: If the same email tries to book the same slot, returns the existing booking.

    **For Voice Agent**: Use this after confirming the slot with the caller.

    Error codes:
    - INVALID_TIMEZONE: The timezone provided is not valid
    - SLOT_UNAVAILABLE: The requested time slot is already booked
    - PAST_DATETIME: Cannot book appointments in the past
    """
    # Validate timezone
    tz = validate_timezone(booking_in.timeZone)
    utc = ZoneInfo("UTC")

    # Parse and convert datetime to UTC
    try:
        local_dt = datetime.strptime(
            f"{booking_in.appointmentDate} {booking_in.appointmentTime}",
            "%Y-%m-%d %H:%M",
        )
        local_dt = local_dt.replace(tzinfo=tz)
        utc_dt = local_dt.astimezone(utc)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": f"Invalid date or time format: {e}",
                "error_code": "INVALID_DATETIME",
            },
        )

    # Check if datetime is in the past
    if utc_dt <= datetime.now(utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": "Cannot book appointments in the past. Please choose a future time slot.",
                "error_code": "PAST_DATETIME",
            },
        )

    # Check for existing booking (idempotency)
    existing = await booking_crud.find_existing_booking(
        db,
        email=booking_in.email,
        appointment_datetime=utc_dt,
    )

    if existing:
        # Return existing booking (idempotent response)
        return BookingResponse(
            success=True,
            booking_id=str(existing.id),
            confirmed_datetime=local_dt.isoformat(),
            message=f"Booking already confirmed for {format_friendly_datetime(utc_dt, tz)}",
        )

    # Check if slot is available
    is_available = await booking_crud.check_slot_available(db, utc_dt)

    if not is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": "This time slot is no longer available. Please choose a different time.",
                "error_code": "SLOT_UNAVAILABLE",
            },
        )

    # Create the booking
    booking = await booking_crud.create_booking(
        db,
        appointment_datetime=utc_dt,
        timezone=booking_in.timeZone,
        first_name=booking_in.firstName,
        last_name=booking_in.lastName,
        email=booking_in.email,
        phone=booking_in.phone,
        contact_id=booking_in.contactId,
    )

    return BookingResponse(
        success=True,
        booking_id=str(booking.id),
        confirmed_datetime=local_dt.isoformat(),
        message=f"Booking confirmed for {format_friendly_datetime(utc_dt, tz)}",
    )
