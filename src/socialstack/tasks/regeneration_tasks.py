import asyncio

from socialstack.celery_app import celery_app
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(bind=True, name="socialstack.tasks.regeneration_tasks.regenerate_content_task", queue="default", max_retries=2)
def regenerate_content_task(self, slot_id: str, business_id: str, platform: str, feedback: str, original_brief: dict, run_id: str):
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.regeneration_service import RegenerationService
        from socialstack.services.run_service import RunService
        from socialstack.ai.client import get_ai_client

        async with get_sessionmaker()() as session:
            run_svc = RunService(session)
            await run_svc.start(run_id, celery_task_id=self.request.id)
            try:
                ai = get_ai_client()
                svc = RegenerationService(session, ai)
                result = await svc.regenerate(
                    slot_id=slot_id,
                    business_id=business_id,
                    platform=platform,
                    feedback=feedback,
                    original_brief=original_brief,
                )
                await run_svc.succeed(run_id, output={"variant_id": result.id, "version": result.version})
                await session.commit()
            except Exception as exc:
                await run_svc.fail(run_id, error={"message": str(exc)})
                await session.commit()
                raise

    _run(_inner())


@celery_app.task(bind=True, name="socialstack.tasks.regeneration_tasks.regenerate_from_feedback_task", queue="default", max_retries=2)
def regenerate_from_feedback_task(self, slot_id: str, feedback: str, platform: str, run_id: str):
    """Called from the /review/slots/{id}/reject endpoint when no original_brief is supplied.
    Loads the latest brief from DB, then runs regeneration."""
    async def _inner():
        from socialstack.db.session import get_sessionmaker
        from socialstack.services.regeneration_service import RegenerationService
        from socialstack.services.run_service import RunService
        from socialstack.ai.client import get_ai_client
        from socialstack.repositories.content_repo import ContentSlotRepository, ContentBriefRepository

        async with get_sessionmaker()() as session:
            run_svc = RunService(session)
            await run_svc.start(run_id, celery_task_id=self.request.id)
            try:
                slot_repo = ContentSlotRepository(session)
                slot = await slot_repo.get_or_raise(slot_id)

                brief_repo = ContentBriefRepository(session)
                brief = await brief_repo.get_latest_for_slot(slot_id)
                if not brief:
                    raise ValueError(f"No brief found for slot {slot_id} — run orchestrate first")

                original_brief = {
                    "hook": brief.hook,
                    "key_message": brief.key_message,
                    "emotional_angle": brief.emotional_angle,
                    "visual_direction": brief.visual_direction,
                    "cta": brief.cta,
                }

                ai = get_ai_client()
                svc = RegenerationService(session, ai)
                result = await svc.regenerate(
                    slot_id=slot_id,
                    business_id=slot.business_id,
                    platform=platform,
                    feedback=feedback,
                    original_brief=original_brief,
                )
                await run_svc.succeed(run_id, output={"variant_id": result.id, "version": result.version})
                await session.commit()
            except Exception as exc:
                await run_svc.fail(run_id, error={"message": str(exc)})
                await session.commit()
                raise

    _run(_inner())
