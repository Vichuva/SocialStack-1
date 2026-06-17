from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from socialstack.repositories.content_repo import ContentSlotRepository, ContentVariantRepository
from socialstack.utils.errors import NotFoundError
from socialstack.utils.logging import get_logger

logger = get_logger(__name__)


class ApprovalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.slot_repo = ContentSlotRepository(session)
        self.variant_repo = ContentVariantRepository(session)

    async def approve_variant(self, variant_id: str) -> dict:
        variant = await self.variant_repo.get(variant_id)
        if not variant:
            raise NotFoundError("ContentVariant", variant_id)

        await self.variant_repo.update(variant, review_status="approved")

        # Check if ALL is_current+is_active variants for this slot are now approved
        slot_promoted = await self._maybe_promote_slot(variant.slot_id)

        logger.info(
            "variant_approved",
            variant_id=variant_id,
            slot_id=variant.slot_id,
            slot_promoted=slot_promoted,
        )
        return {"approved": True, "slot_promoted": slot_promoted}

    async def reject_variant(
        self, variant_id: str, feedback: str, regenerate: bool, platform: str | None = None
    ) -> dict:
        variant = await self.variant_repo.get(variant_id)
        if not variant:
            raise NotFoundError("ContentVariant", variant_id)

        await self.variant_repo.update(
            variant,
            review_status="rejected",
            is_current=False,
            is_active=False,
            feedback_text=feedback,
        )

        # If the slot was fully approved, revert it to pending_review
        slot = await self.slot_repo.get(variant.slot_id)
        if slot and slot.status == "approved":
            await self.slot_repo.update(slot, status="pending_review", approved_at=None)

        regenerated = False
        if regenerate:
            from socialstack.tasks.regeneration_tasks import regenerate_from_feedback_task
            from socialstack.services.run_service import RunService

            run_svc = RunService(self.session)
            run = await run_svc.create(
                workflow="WF-REGEN",
                business_id=variant.business_id,
                trigger_kind="api",
                input_data={"slot_id": variant.slot_id, "feedback": feedback},
            )
            regenerate_from_feedback_task.delay(
                slot_id=variant.slot_id,
                feedback=feedback,
                platform=platform or variant.platform,
                run_id=run.id,
            )
            regenerated = True

        logger.info(
            "variant_rejected",
            variant_id=variant_id,
            slot_id=variant.slot_id,
            regenerated=regenerated,
        )
        return {"rejected": True, "regenerated": regenerated}

    async def approve_all(self, business_id: str, calendar_id: str | None = None) -> dict:
        slots = await self.slot_repo.get_pending_review(business_id)
        if calendar_id:
            slots = [s for s in slots if s.calendar_id == calendar_id]

        approved_count = 0
        for slot in slots:
            variants = await self.variant_repo.get_current_for_slot(slot.id)
            for v in variants:
                if v.review_status != "approved":
                    await self.variant_repo.update(v, review_status="approved")
            await self.slot_repo.update(
                slot,
                status="approved",
                approved_at=datetime.now(timezone.utc),
            )
            approved_count += 1

        logger.info(
            "approve_all_complete",
            business_id=business_id,
            calendar_id=calendar_id,
            approved_count=approved_count,
        )
        return {"approved_count": approved_count}

    async def approve_all_for_slot(self, slot_id: str) -> None:
        """Used by generation service when auto_approve=True."""
        variants = await self.variant_repo.get_current_for_slot(slot_id)
        for v in variants:
            await self.variant_repo.update(v, review_status="approved")
        await self._maybe_promote_slot(slot_id)

    async def _maybe_promote_slot(self, slot_id: str) -> bool:
        """Promote slot to 'approved' if every is_current+is_active variant is approved."""
        current_variants = await self.variant_repo.get_current_for_slot(slot_id)
        if not current_variants:
            return False
        all_approved = all(v.review_status == "approved" for v in current_variants)
        if all_approved:
            slot = await self.slot_repo.get(slot_id)
            if slot and slot.status not in ("approved", "published"):
                await self.slot_repo.update(
                    slot,
                    status="approved",
                    approved_at=datetime.now(timezone.utc),
                )
                return True
        return False
