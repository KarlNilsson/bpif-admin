from fastapi import APIRouter, HTTPException, status

from app.core.database import DbSession
from app.health import service
from app.health.schemas import HealthRead

router = APIRouter(prefix='/health', tags=['health'])


@router.get('', response_model=HealthRead)
async def get_health(session: DbSession) -> HealthRead:
    if not await service.check_database(session):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database unavailable',
        )
    return HealthRead(status='ok', database='ok')
