from fastapi import APIRouter, status

from socialstack.dependencies import DbSession
from socialstack.repositories.business_repo import BusinessRepository
from socialstack.repositories.calendar_repo import CalendarRepository
from socialstack.schemas.calendar import (
    CalendarCreate,
    CalendarDayResponse,
    CalendarResponse,
    GenerateThemesRequest,
    GenerateThemesResponse,
)

router = APIRouter(tags=["calendars"])


@router.post("", response_model=CalendarResponse, status_code=status.HTTP_201_CREATED)
async def create_calendar(body: CalendarCreate, db: DbSession):
    biz_repo = BusinessRepository(db)
    await biz_repo.get_or_raise(body.business_id)

    repo = CalendarRepository(db)
    calendar = await repo.create(
        business_id=body.business_id,
        month=body.month,
        year=body.year,
    )
    return CalendarResponse(
        id=calendar.id,
        business_id=calendar.business_id,
        month=calendar.month,
        year=calendar.year,
        status=calendar.status,
        days=[],
    )


@router.get("/{calendar_id}", response_model=CalendarResponse)
async def get_calendar(calendar_id: str, db: DbSession):
    repo = CalendarRepository(db)
    calendar = await repo.get_with_days(calendar_id)
    if not calendar:
        from socialstack.utils.errors import NotFoundError
        raise NotFoundError("Calendar", calendar_id)

    days = [
        CalendarDayResponse(
            id=d.id,
            date=d.date,
            day_number=d.day_number,
            theme=d.theme,
            objective=d.objective,
            post_idea=d.post_idea,
        )
        for d in (calendar.days or [])
    ]
    return CalendarResponse(
        id=calendar.id,
        business_id=calendar.business_id,
        month=calendar.month,
        year=calendar.year,
        status=calendar.status,
        days=days,
    )


@router.post("/{calendar_id}/generate-themes", response_model=GenerateThemesResponse)
async def generate_themes(calendar_id: str, body: GenerateThemesRequest, db: DbSession):
    repo = CalendarRepository(db)
    calendar = await repo.get_or_raise(calendar_id)

    from socialstack.services.run_service import RunService
    run_svc = RunService(db)
    run = await run_svc.create(
        workflow="WF-CAL",
        business_id=calendar.business_id,
        trigger_kind="api",
        input_data={"calendar_id": calendar_id},
    )

    from socialstack.tasks.generation_tasks import generate_calendar_themes_task
    generate_calendar_themes_task.delay(calendar_id=calendar_id, run_id=run.id)

    return GenerateThemesResponse(
        run_id=run.id,
        status="queued",
        calendar_id=calendar_id,
    )
