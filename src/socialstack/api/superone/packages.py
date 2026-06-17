from typing import Annotated

from fastapi import APIRouter, Depends

from socialstack.api.superone.deps import RequestContext, envelope, get_context
from socialstack.dependencies import DbSession
from socialstack.repositories.packages_repo import ContentPackageRepository

router = APIRouter(tags=["packages"])
Ctx = Annotated[RequestContext, Depends(get_context)]


def _fmt_package(pkg) -> dict:
    return {
        "id": pkg.id,
        "name": pkg.name,
        "billing_cycle": pkg.billing_cycle,
        "is_active": pkg.is_active,
        "items": [
            {
                "id": item.id,
                "content_types": item.content_types,
                "max_posts": item.max_posts,
                "period": item.period,
            }
            for item in (pkg.items or [])
        ],
    }


@router.get("/packages")
async def list_packages(ctx: Ctx, db: DbSession):
    repo = ContentPackageRepository(db)
    packages = await repo.list_active()
    return envelope([_fmt_package(p) for p in packages], ctx.request_id)
