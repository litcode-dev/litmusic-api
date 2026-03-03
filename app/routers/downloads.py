from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.services import download_service
from app.schemas.download import DownloadedLoopItem
from app.schemas.common import success

router = APIRouter(prefix="/downloads", tags=["downloads"])


@router.get("")
async def get_download_history(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return all distinct loops the authenticated user has downloaded."""
    rows, total = await download_service.get_user_download_history(
        db, user.id, page, page_size
    )
    items = [DownloadedLoopItem.model_validate(dict(row)).model_dump() for row in rows]
    return success({
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    })
