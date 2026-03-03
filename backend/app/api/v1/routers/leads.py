"""FastAPI router for Lead endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.crud import lead_crud
from app.models.enums import (
    LeadStage,
    LeadSource,
    LeadTemperature,
    LeadIndustry,
    LeadTerritory,
    EmployeeCount,
)
from app.models.user_model import User
from app.schemas.lead_schema import (
    EmployeeCountInfo,
    LeadCreate,
    LeadIndustryInfo,
    LeadListResponse,
    LeadMetadataResponse,
    LeadResponse,
    LeadsByStageResponse,
    LeadSourceInfo,
    LeadStageInfo,
    LeadStatusInfo,
    LeadTemperatureInfo,
    LeadTerritoryInfo,
    LeadUpdate,
    TagCreate,
    TagWithIdResponse,
)

router = APIRouter()


@router.get("", response_model=LeadListResponse)
async def list_leads(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: str | None = Query(default=None, description="Search in name, email, company"),
    status: str | None = Query(default=None, description="Filter by status"),
    stage: LeadStage | None = Query(default=None, description="Filter by stage"),
    temperature: LeadTemperature | None = Query(default=None, description="Filter by temperature"),
    lead_owner: str | None = Query(default=None, description="Filter by owner email"),
    source: LeadSource | None = Query(default=None, description="Filter by source"),
    tags: str | None = Query(default=None, description="Comma-separated tag names"),
    order_by: str = Query(default="created_at", description="Field to order by"),
    order_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> LeadListResponse:
    """
    Get paginated list of leads with optional filters.

    Query parameters:
    - search: Search in first_name, last_name, email, company
    - stage: Filter by lead stage (new, contacted, qualified, etc.)
    - temperature: Filter by lead temperature (hot, warm, cold)
    - source: Filter by lead source
    - lead_owner: Filter by assigned owner email
    - tags: Comma-separated list of tag names
    - order_by: Field to sort by (default: created_at)
    - order_dir: Sort direction (asc or desc)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    """
    # Parse tags from comma-separated string
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    # Map status to stage if provided
    filter_stage = stage
    if status and not stage:
        status_to_stage = {s.label.lower(): s for s in LeadStage}
        filter_stage = status_to_stage.get(status.lower())

    leads, total_count = await lead_crud.get_leads(
        db,
        user_id=current_user.id,
        search=search,
        stage=filter_stage,
        temperature=temperature.value if temperature else None,
        source=source.value if source else None,
        lead_owner=lead_owner,
        tags=tag_list,
        order_by=order_by,
        order_dir=order_dir,
        page=page,
        page_size=page_size,
    )

    total_pages = (total_count + page_size - 1) // page_size

    return LeadListResponse(
        data=[LeadResponse.model_validate(lead) for lead in leads],
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/by-stage", response_model=LeadsByStageResponse)
async def get_leads_by_stage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadsByStageResponse:
    """Get all leads grouped by their stage."""
    grouped = await lead_crud.get_leads_by_stage(db, user_id=current_user.id)

    return LeadsByStageResponse(
        new=[LeadResponse.model_validate(l) for l in grouped.get("new", [])],
        contacted=[LeadResponse.model_validate(l) for l in grouped.get("contacted", [])],
        qualified=[LeadResponse.model_validate(l) for l in grouped.get("qualified", [])],
        proposal=[LeadResponse.model_validate(l) for l in grouped.get("proposal", [])],
        negotiation=[LeadResponse.model_validate(l) for l in grouped.get("negotiation", [])],
        won=[LeadResponse.model_validate(l) for l in grouped.get("won", [])],
        lost=[LeadResponse.model_validate(l) for l in grouped.get("lost", [])],
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadResponse:
    """Get a single lead by ID with full details."""
    lead = await lead_crud.get_lead(db, lead_id=lead_id, user_id=current_user.id)
    return LeadResponse.model_validate(lead)


@router.post("", response_model=LeadResponse, status_code=201)
async def create_lead(
    lead_in: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadResponse:
    """Create a new lead."""
    lead = await lead_crud.create_lead(db, lead_in=lead_in, user_id=current_user.id)
    return LeadResponse.model_validate(lead)


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: UUID,
    lead_in: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeadResponse:
    """
    Update an existing lead.

    If stage is changed, a stage history record is created.
    Include stage_change_notes for the history record.
    """
    lead = await lead_crud.update_lead(
        db,
        lead_id=lead_id,
        lead_in=lead_in,
        user_id=current_user.id,
        changed_by=current_user.id,
    )
    return LeadResponse.model_validate(lead)


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Soft delete a lead (sets deleted_at and is_active=False)."""
    await lead_crud.delete_lead(db, lead_id=lead_id, user_id=current_user.id)
    return {"success": True}


# ============== Stage/Status Endpoints ==============

@router.get("/meta/stages", response_model=list[LeadStageInfo])
async def get_lead_stages() -> list[LeadStageInfo]:
    """Get all available lead stages with their labels and colors."""
    return [
        LeadStageInfo(name=stage.value, label=stage.label, color=stage.color)
        for stage in LeadStage
    ]


@router.get("/meta/statuses", response_model=list[LeadStatusInfo])
async def get_lead_statuses() -> list[LeadStatusInfo]:
    """Get all available lead statuses (derived from stages)."""
    return [
        LeadStatusInfo(name=stage.label, color=stage.color)
        for stage in LeadStage
    ]


@router.get("/meta/sources", response_model=list[LeadSourceInfo])
async def get_lead_sources() -> list[LeadSourceInfo]:
    """Get all available lead sources."""
    return [
        LeadSourceInfo(value=source.value, label=source.value)
        for source in LeadSource
    ]


@router.get("/meta/temperatures", response_model=list[LeadTemperatureInfo])
async def get_lead_temperatures() -> list[LeadTemperatureInfo]:
    """Get all available lead temperatures."""
    return [
        LeadTemperatureInfo(value=temp.value, label=temp.label, color=temp.color)
        for temp in LeadTemperature
    ]


@router.get("/meta/industries", response_model=list[LeadIndustryInfo])
async def get_lead_industries() -> list[LeadIndustryInfo]:
    """Get all available industries."""
    return [
        LeadIndustryInfo(value=industry.value, label=industry.value)
        for industry in LeadIndustry
    ]


@router.get("/meta/territories", response_model=list[LeadTerritoryInfo])
async def get_lead_territories() -> list[LeadTerritoryInfo]:
    """Get all available territories."""
    return [
        LeadTerritoryInfo(value=territory.value, label=territory.value)
        for territory in LeadTerritory
    ]


@router.get("/meta/employee-counts", response_model=list[EmployeeCountInfo])
async def get_employee_counts() -> list[EmployeeCountInfo]:
    """Get all available employee count ranges."""
    return [
        EmployeeCountInfo(value=ec.value, label=ec.value)
        for ec in EmployeeCount
    ]


@router.get("/meta/all", response_model=LeadMetadataResponse)
async def get_all_metadata() -> LeadMetadataResponse:
    """Get all lead metadata in one request (for dropdowns)."""
    return LeadMetadataResponse(
        stages=[
            LeadStageInfo(name=stage.value, label=stage.label, color=stage.color)
            for stage in LeadStage
        ],
        statuses=[
            LeadStatusInfo(name=stage.label, color=stage.color)
            for stage in LeadStage
        ],
        sources=[
            LeadSourceInfo(value=source.value, label=source.value)
            for source in LeadSource
        ],
        temperatures=[
            LeadTemperatureInfo(value=temp.value, label=temp.label, color=temp.color)
            for temp in LeadTemperature
        ],
        industries=[
            LeadIndustryInfo(value=industry.value, label=industry.value)
            for industry in LeadIndustry
        ],
        territories=[
            LeadTerritoryInfo(value=territory.value, label=territory.value)
            for territory in LeadTerritory
        ],
        employee_counts=[
            EmployeeCountInfo(value=ec.value, label=ec.value)
            for ec in EmployeeCount
        ],
    )


# ============== Tag Endpoints ==============

@router.get("/tags", response_model=list[TagWithIdResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TagWithIdResponse]:
    """Get all tags for the current user."""
    tags = await lead_crud.get_tags(db, user_id=current_user.id)
    return [TagWithIdResponse.model_validate(tag) for tag in tags]


@router.post("/tags", response_model=TagWithIdResponse, status_code=201)
async def create_tag(
    tag_in: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TagWithIdResponse:
    """Create a new tag."""
    tag = await lead_crud.create_tag(
        db,
        name=tag_in.name,
        color=tag_in.color,
        user_id=current_user.id,
    )
    return TagWithIdResponse.model_validate(tag)


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete a tag."""
    await lead_crud.delete_tag(db, tag_id=tag_id, user_id=current_user.id)
    return {"success": True}
