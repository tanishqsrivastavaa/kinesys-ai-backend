from fastapi import APIRouter
from .routers import auth, leads, calls, bookings, ai_calling, calendar
from app.models.enums import LeadStage
from app.schemas.lead_schema import LeadStageInfo, LeadStatusInfo

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(leads.router, prefix="/leads", tags=["leads"])
router.include_router(calls.router, prefix="/calls", tags=["calls"])
router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
router.include_router(ai_calling.router, prefix="/ai-calling", tags=["ai-calling"])
# router.include_router(mail.router, prefix="/mails", tags=["mails"])
router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])


# Top-level stage/status endpoints for backward compatibility
@router.get("/lead-stages", response_model=list[LeadStageInfo], tags=["leads"])
async def get_lead_stages() -> list[LeadStageInfo]:
    """Get all available lead stages with their labels and colors."""
    return [
        LeadStageInfo(name=stage.value, label=stage.label, color=stage.color)
        for stage in LeadStage
    ]


@router.get("/lead-statuses", response_model=list[LeadStatusInfo], tags=["leads"])
async def get_lead_statuses() -> list[LeadStatusInfo]:
    """Get all available lead statuses (derived from stages)."""
    return [
        LeadStatusInfo(name=stage.label, color=stage.color)
        for stage in LeadStage
    ]
