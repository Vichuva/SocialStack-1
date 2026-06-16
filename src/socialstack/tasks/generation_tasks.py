"""
Generation Celery tasks — WF-CAL, WF-BRIEF, WF-CAPTION, WF-ASSET, WF-GENORCH, WF-MVAR.
Service implementations go in src/socialstack/services/. These tasks are thin wrappers
that handle async→sync bridging and session lifecycle.
"""

import asyncio

from socialstack.celery_app import celery_app
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


def _run(coro):
    """Run an async coroutine in a new event loop (for Celery sync context)."""
    return asyncio.run(coro)


@celery_app.task(bind=True, name="socialstack.tasks.generation_tasks.generate_calendar_themes_task", queue="default", max_retries=2)
def generate_calendar_themes_task(self, calendar_id: str, run_id: str):
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.calendar_service import CalendarService
        from socialstack.services.run_service import RunService
        from socialstack.ai.client import get_ai_client

        async with get_sessionmaker()() as session:
            run_svc = RunService(session)
            await run_svc.start(run_id, celery_task_id=self.request.id)
            try:
                ai = get_ai_client()
                svc = CalendarService(session, ai)
                result = await svc.generate_themes(calendar_id)
                await run_svc.succeed(run_id, output=result)
                await session.commit()
            except Exception as exc:
                await run_svc.fail(run_id, error={"message": str(exc), "type": type(exc).__name__})
                await session.commit()
                raise

    _run(_inner())


@celery_app.task(bind=True, name="socialstack.tasks.generation_tasks.generate_content_task", queue="default", max_retries=1)
def generate_content_task(self, calendar_id: str, business_id: str, platforms: list, generate_images: bool, run_id: str, calendar_day_id: str | None = None):
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.generation_service import GenerationService
        from socialstack.services.run_service import RunService
        from socialstack.ai.client import get_ai_client

        async with get_sessionmaker()() as session:
            run_svc = RunService(session)
            await run_svc.start(run_id, celery_task_id=self.request.id)
            try:
                ai = get_ai_client()
                svc = GenerationService(session, ai)
                result = await svc.orchestrate(
                    calendar_id=calendar_id,
                    business_id=business_id,
                    platforms=platforms,
                    generate_images=generate_images,
                    calendar_day_id=calendar_day_id,
                )
                await run_svc.succeed(run_id, output=result)
                await session.commit()
            except Exception as exc:
                await run_svc.fail(run_id, error={"message": str(exc), "type": type(exc).__name__})
                await session.commit()
                raise

    _run(_inner())


@celery_app.task(bind=True, name="socialstack.tasks.generation_tasks.generate_brief_task", queue="default", max_retries=3)
def generate_brief_task(self, slot_id: str, business_id: str, day: dict, run_id: str):
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.brief_service import BriefService
        from socialstack.services.run_service import RunService
        from socialstack.ai.client import get_ai_client

        async with get_sessionmaker()() as session:
            run_svc = RunService(session)
            await run_svc.start(run_id, celery_task_id=self.request.id)
            try:
                ai = get_ai_client()
                svc = BriefService(session, ai)
                result = await svc.generate(slot_id=slot_id, business_id=business_id, day=day)
                await run_svc.succeed(run_id, output={"brief_id": result.id})
                await session.commit()
            except Exception as exc:
                await run_svc.fail(run_id, error={"message": str(exc)})
                await session.commit()
                raise

    _run(_inner())


@celery_app.task(bind=True, name="socialstack.tasks.generation_tasks.generate_caption_task", queue="default", max_retries=3)
def generate_caption_task(self, slot_id: str, business_id: str, platform: str, brief: dict, run_id: str):
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.caption_service import CaptionService
        from socialstack.services.run_service import RunService
        from socialstack.ai.client import get_ai_client

        async with get_sessionmaker()() as session:
            run_svc = RunService(session)
            await run_svc.start(run_id, celery_task_id=self.request.id)
            try:
                ai = get_ai_client()
                svc = CaptionService(session, ai)
                result = await svc.generate(slot_id=slot_id, business_id=business_id, platform=platform, brief=brief)
                await run_svc.succeed(run_id, output={"variant_id": result.id})
                await session.commit()
            except Exception as exc:
                await run_svc.fail(run_id, error={"message": str(exc)})
                await session.commit()
                raise

    _run(_inner())


@celery_app.task(bind=True, name="socialstack.tasks.generation_tasks.generate_asset_task", queue="images", max_retries=2)
def generate_asset_task(self, slot_id: str, business_id: str, platform: str, theme: str, brief: dict, run_id: str):
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.asset_service import AssetService
        from socialstack.services.run_service import RunService
        from socialstack.ai.client import get_ai_client
        from socialstack.utils.storage import get_storage

        async with get_sessionmaker()() as session:
            run_svc = RunService(session)
            await run_svc.start(run_id, celery_task_id=self.request.id)
            try:
                ai = get_ai_client()
                storage = get_storage()
                svc = AssetService(session, ai, storage)
                result = await svc.generate(slot_id=slot_id, business_id=business_id, platform=platform, theme=theme, brief=brief)
                await run_svc.succeed(run_id, output={"asset_id": result.id, "url": result.storage_url})
                await session.commit()
            except Exception as exc:
                await run_svc.fail(run_id, error={"message": str(exc)})
                await session.commit()
                raise

    _run(_inner())


@celery_app.task(bind=True, name="socialstack.tasks.generation_tasks.generate_multi_variant_task", queue="default", max_retries=2)
def generate_multi_variant_task(self, slot_id: str, business_id: str, platform: str, brief: dict, variant_count: int, run_id: str):
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.variant_service import VariantService
        from socialstack.services.run_service import RunService
        from socialstack.ai.client import get_ai_client

        async with get_sessionmaker()() as session:
            run_svc = RunService(session)
            await run_svc.start(run_id, celery_task_id=self.request.id)
            try:
                ai = get_ai_client()
                svc = VariantService(session, ai)
                results = await svc.generate_multi(slot_id=slot_id, business_id=business_id, platform=platform, brief=brief, count=variant_count)
                await run_svc.succeed(run_id, output={"variant_ids": [r.id for r in results], "count": len(results)})
                await session.commit()
            except Exception as exc:
                await run_svc.fail(run_id, error={"message": str(exc)})
                await session.commit()
                raise

    _run(_inner())
