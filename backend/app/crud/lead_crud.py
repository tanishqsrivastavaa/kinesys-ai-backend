"""CRUD operations for Lead module."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.enums import LeadStage
from app.models.lead_model import Lead, LeadStageHistory, LeadTagLink, Tag
from app.schemas.lead_schema import LeadCreate, LeadUpdate


async def get_leads(
    db: AsyncSession,
    user_id: UUID,
    *,
    search: str | None = None,
    stage: LeadStage | None = None,
    temperature: str | None = None,
    source: str | None = None,
    lead_owner: str | None = None,
    tags: list[str] | None = None,
    order_by: str = "created_at",
    order_dir: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Lead], int]:
    """Get paginated list of leads with filters."""
    # Base query - only active leads for this user
    query = (
        select(Lead)
        .where(Lead.user_id == user_id, Lead.is_active == True)
        .options(selectinload(Lead.tags), selectinload(Lead.owner), selectinload(Lead.assignee))
    )

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Lead.first_name.ilike(search_term),
                Lead.last_name.ilike(search_term),
                Lead.email.ilike(search_term),
                Lead.company.ilike(search_term),
                Lead.organization.ilike(search_term),
            )
        )

    # Apply stage filter
    if stage:
        stage_value = stage.value if hasattr(stage, "value") else stage
        query = query.where(Lead.stage == stage_value)

    # Apply temperature filter
    if temperature:
        query = query.where(Lead.temperature == temperature)

    # Apply source filter
    if source:
        query = query.where(Lead.source == source)

    # Apply assigned_to filter by email
    if lead_owner:
        from app.models.user_model import User
        query = query.join(User, Lead.assigned_to == User.id).where(User.email == lead_owner)

    # Apply tags filter
    if tags:
        query = query.join(LeadTagLink).join(Tag).where(Tag.name.in_(tags))

    # Get total count before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.exec(count_query)
    total_count = total_result.one()

    # Apply ordering
    order_column = getattr(Lead, order_by, Lead.created_at)
    if order_dir.lower() == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.exec(query)
    leads = result.unique().all()

    return list(leads), total_count


async def get_lead(
    db: AsyncSession,
    lead_id: UUID,
    user_id: UUID,
) -> Lead:
    """Get a single lead by ID."""
    query = (
        select(Lead)
        .where(Lead.id == lead_id, Lead.user_id == user_id, Lead.is_active == True)
        .options(
            selectinload(Lead.tags),
            selectinload(Lead.owner),
            selectinload(Lead.assignee),
            selectinload(Lead.stage_history),
        )
    )
    result = await db.exec(query)
    lead = result.first()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with id {lead_id} not found",
        )

    return lead


async def create_lead(
    db: AsyncSession,
    lead_in: LeadCreate,
    user_id: UUID,
) -> Lead:
    """Create a new lead."""
    # Extract tag_ids before creating lead
    tag_ids = lead_in.tag_ids
    lead_data = lead_in.model_dump(exclude={"tag_ids"})

    # Create lead
    lead = Lead(**lead_data, user_id=user_id)
    db.add(lead)
    await db.flush()

    # Add tags if provided
    if tag_ids:
        await _update_lead_tags(db, lead.id, tag_ids, user_id)

    await db.commit()
    await db.refresh(lead)

    # Reload with relationships
    return await get_lead(db, lead.id, user_id)


async def update_lead(
    db: AsyncSession,
    lead_id: UUID,
    lead_in: LeadUpdate,
    user_id: UUID,
    changed_by: UUID,
) -> Lead:
    """Update an existing lead."""
    lead = await get_lead(db, lead_id, user_id)

    # Track stage change
    old_stage = lead.stage

    # Update fields
    update_data = lead_in.model_dump(exclude_unset=True, exclude={"tag_ids", "stage_change_notes"})
    for field, value in update_data.items():
        setattr(lead, field, value)

    # Update last activity
    lead.last_activity_at = datetime.now(timezone.utc)

    # Handle stage change history
    new_stage = lead_in.stage.value if hasattr(lead_in.stage, "value") else lead_in.stage
    if new_stage and new_stage != old_stage:
        await record_stage_change(
            db,
            lead_id=lead.id,
            from_stage=old_stage,
            to_stage=new_stage,
            changed_by=changed_by,
            notes=lead_in.stage_change_notes,
        )

    # Update tags if provided
    if lead_in.tag_ids is not None:
        await _update_lead_tags(db, lead.id, lead_in.tag_ids, user_id)

    await db.commit()
    await db.refresh(lead)

    return await get_lead(db, lead.id, user_id)


async def delete_lead(
    db: AsyncSession,
    lead_id: UUID,
    user_id: UUID,
) -> bool:
    """Soft delete a lead."""
    lead = await get_lead(db, lead_id, user_id)

    lead.deleted_at = datetime.now(timezone.utc)
    lead.is_active = False

    await db.commit()
    return True


async def get_leads_by_stage(
    db: AsyncSession,
    user_id: UUID,
) -> dict[str, list[Lead]]:
    """Get all leads grouped by stage."""
    query = (
        select(Lead)
        .where(Lead.user_id == user_id, Lead.is_active == True)
        .options(selectinload(Lead.tags), selectinload(Lead.owner), selectinload(Lead.assignee))
        .order_by(Lead.created_at.desc())
    )

    result = await db.exec(query)
    leads = result.unique().all()

    # Group by stage
    grouped: dict[str, list[Lead]] = {stage.value: [] for stage in LeadStage}
    for lead in leads:
        # lead.stage is now a string, not an enum
        stage_key = lead.stage if isinstance(lead.stage, str) else lead.stage.value
        if stage_key in grouped:
            grouped[stage_key].append(lead)

    return grouped


async def record_stage_change(
    db: AsyncSession,
    lead_id: UUID,
    from_stage: str | None,
    to_stage: str,
    changed_by: UUID,
    notes: str | None = None,
) -> LeadStageHistory:
    """Record a stage change in history."""
    # Convert enum to string value if needed
    from_stage_str = from_stage.value if hasattr(from_stage, "value") else from_stage
    to_stage_str = to_stage.value if hasattr(to_stage, "value") else to_stage

    history = LeadStageHistory(
        lead_id=lead_id,
        from_stage=from_stage_str,
        to_stage=to_stage_str,
        changed_by=changed_by,
        notes=notes,
    )
    db.add(history)
    await db.flush()
    return history


async def _update_lead_tags(
    db: AsyncSession,
    lead_id: UUID,
    tag_ids: list[UUID],
    user_id: UUID,
) -> None:
    """Update lead tags by removing old and adding new."""
    # Remove existing tag links
    delete_query = select(LeadTagLink).where(LeadTagLink.lead_id == lead_id)
    result = await db.exec(delete_query)
    existing_links = result.all()
    for link in existing_links:
        await db.delete(link)

    # Verify tags belong to user and add new links
    if tag_ids:
        tags_query = select(Tag).where(Tag.id.in_(tag_ids), Tag.user_id == user_id)
        tags_result = await db.exec(tags_query)
        valid_tags = tags_result.all()

        for tag in valid_tags:
            link = LeadTagLink(lead_id=lead_id, tag_id=tag.id)
            db.add(link)


# ============== Tag CRUD ==============

async def get_tags(db: AsyncSession, user_id: UUID) -> list[Tag]:
    """Get all tags for a user."""
    query = select(Tag).where(Tag.user_id == user_id).order_by(Tag.name)
    result = await db.exec(query)
    return list(result.all())


async def create_tag(
    db: AsyncSession,
    name: str,
    color: str,
    user_id: UUID,
) -> Tag:
    """Create a new tag."""
    tag = Tag(name=name, color=color, user_id=user_id)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def delete_tag(db: AsyncSession, tag_id: UUID, user_id: UUID) -> bool:
    """Delete a tag."""
    query = select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
    result = await db.exec(query)
    tag = result.first()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag with id {tag_id} not found",
        )

    await db.delete(tag)
    await db.commit()
    return True
