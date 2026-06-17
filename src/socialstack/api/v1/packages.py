from fastapi import APIRouter

from socialstack.dependencies import DbSession
from socialstack.repositories.packages_repo import ContentPackageRepository
from socialstack.schemas.packages import ContentPackageResponse
from socialstack.utils.errors import NotFoundError

router = APIRouter(tags=["packages"])


@router.get("", response_model=list[ContentPackageResponse])
async def list_packages(db: DbSession):
    """List all active content packages with their items."""
    repo = ContentPackageRepository(db)
    packages = await repo.list_active()
    return [
        ContentPackageResponse(
            id=p.id,
            name=p.name,
            billing_cycle=p.billing_cycle,
            posts_per_week=p.posts_per_week,
            content_types=p.content_types or [],
            is_active=p.is_active,
            items=[
                {
                    "id": item.id,
                    "package_id": item.package_id,
                    "content_types": item.content_types or [],
                    "max_posts": item.max_posts,
                    "period": item.period,
                }
                for item in (p.items or [])
            ],
        )
        for p in packages
    ]


@router.get("/{package_id}", response_model=ContentPackageResponse)
async def get_package(package_id: str, db: DbSession):
    """Get a single package with its items."""
    repo = ContentPackageRepository(db)
    pkg = await repo.get_with_items(package_id)
    if not pkg:
        raise NotFoundError("ContentPackage", package_id)
    return ContentPackageResponse(
        id=pkg.id,
        name=pkg.name,
        billing_cycle=pkg.billing_cycle,
        posts_per_week=pkg.posts_per_week,
        content_types=pkg.content_types or [],
        is_active=pkg.is_active,
        items=[
            {
                "id": item.id,
                "package_id": item.package_id,
                "content_types": item.content_types or [],
                "max_posts": item.max_posts,
                "period": item.period,
            }
            for item in (pkg.items or [])
        ],
    )
