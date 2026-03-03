"""CRUD operations for Booking module."""

from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.booking_model import Booking, BookingStatus


async def get_booked_slots(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> list[datetime]:
    """
    Get all booked appointment datetimes within a date range.

    Args:
        db: Database session
        start_date: Start of range (UTC)
        end_date: End of range (UTC)

    Returns:
        List of booked datetime slots in UTC
    """
    query = (
        select(Booking.appointment_datetime)
        .where(
            Booking.appointment_datetime >= start_date,
            Booking.appointment_datetime < end_date,
            Booking.is_active == True,
            Booking.status.in_([BookingStatus.CONFIRMED.value, BookingStatus.COMPLETED.value]),
        )
    )
    result = await db.exec(query)
    return list(result.all())


async def check_slot_available(
    db: AsyncSession,
    appointment_datetime: datetime,
) -> bool:
    """
    Check if a specific time slot is available.

    Args:
        db: Database session
        appointment_datetime: The datetime to check (UTC)

    Returns:
        True if slot is available, False otherwise
    """
    query = (
        select(Booking)
        .where(
            Booking.appointment_datetime == appointment_datetime,
            Booking.is_active == True,
            Booking.status.in_([BookingStatus.CONFIRMED.value, BookingStatus.COMPLETED.value]),
        )
    )
    result = await db.exec(query)
    existing = result.first()
    return existing is None


async def find_existing_booking(
    db: AsyncSession,
    email: str,
    appointment_datetime: datetime,
) -> Booking | None:
    """
    Find an existing booking for idempotency check.

    Checks if the same email already has a booking at the exact same time.

    Args:
        db: Database session
        email: Customer email
        appointment_datetime: The appointment datetime (UTC)

    Returns:
        Existing booking if found, None otherwise
    """
    query = (
        select(Booking)
        .where(
            Booking.email == email,
            Booking.appointment_datetime == appointment_datetime,
            Booking.is_active == True,
            Booking.status == BookingStatus.CONFIRMED.value,
        )
    )
    result = await db.exec(query)
    return result.first()


async def create_booking(
    db: AsyncSession,
    *,
    appointment_datetime: datetime,
    timezone: str,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    contact_id: UUID | None = None,
) -> Booking:
    """
    Create a new booking.

    Args:
        db: Database session
        appointment_datetime: Appointment time in UTC
        timezone: Original timezone string
        first_name: Customer first name
        last_name: Customer last name
        email: Customer email
        phone: Customer phone
        contact_id: Optional link to lead/contact

    Returns:
        Created booking
    """
    booking = Booking(
        appointment_datetime=appointment_datetime,
        timezone=timezone,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        contact_id=contact_id,
        status=BookingStatus.CONFIRMED.value,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


async def get_booking(
    db: AsyncSession,
    booking_id: UUID,
) -> Booking | None:
    """Get a booking by ID."""
    query = select(Booking).where(Booking.id == booking_id, Booking.is_active == True)
    result = await db.exec(query)
    return result.first()


async def cancel_booking(
    db: AsyncSession,
    booking_id: UUID,
) -> Booking | None:
    """Cancel a booking by ID."""
    booking = await get_booking(db, booking_id)
    if booking:
        booking.status = BookingStatus.CANCELLED.value
        await db.commit()
        await db.refresh(booking)
    return booking


def generate_available_slots(
    booked_slots_utc: list[datetime],
    timezone_str: str,
    days: int = 7,
    start_hour: int = 9,
    end_hour: int = 17,
    slot_duration_minutes: int = 60,
) -> dict[str, list[str]]:
    """
    Generate available time slots for the next N days.

    Args:
        booked_slots_utc: List of already booked slots in UTC
        timezone_str: Target timezone for display
        days: Number of days to show availability
        start_hour: Business start hour (in target timezone)
        end_hour: Business end hour (in target timezone)
        slot_duration_minutes: Duration of each slot

    Returns:
        Dictionary mapping date strings to lists of available time strings
    """
    tz = ZoneInfo(timezone_str)
    utc = ZoneInfo("UTC")

    # Convert booked slots to target timezone for comparison
    booked_set = {
        slot.astimezone(tz).replace(tzinfo=None)
        for slot in booked_slots_utc
    }

    # Get current time in target timezone
    now = datetime.now(tz)

    # Start from tomorrow if current time is past business hours
    if now.hour >= end_hour:
        start_date = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    available: dict[str, list[str]] = {}

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)

        # Skip weekends (Saturday=5, Sunday=6)
        if current_date.weekday() >= 5:
            continue

        date_str = current_date.strftime("%Y-%m-%d")
        times: list[str] = []

        # Generate slots for this day
        slot_time = current_date.replace(hour=start_hour, minute=0)
        end_time = current_date.replace(hour=end_hour, minute=0)

        while slot_time < end_time:
            # Skip if slot is in the past
            slot_with_tz = slot_time.replace(tzinfo=tz)
            if slot_with_tz <= now:
                slot_time += timedelta(minutes=slot_duration_minutes)
                continue

            # Check if slot is booked
            if slot_time not in booked_set:
                times.append(slot_time.strftime("%H:%M"))

            slot_time += timedelta(minutes=slot_duration_minutes)

        if times:
            available[date_str] = times

    return available
