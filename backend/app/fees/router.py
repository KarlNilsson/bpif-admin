from fastapi import APIRouter

from app.core.database import DbSession
from app.fees import service
from app.fees.schemas import FeeRead

admin_router = APIRouter(prefix='/fees', tags=['fees'])


@admin_router.post('/{fee_id}/mark-unpaid')
async def mark_unpaid(fee_id: int, session: DbSession) -> FeeRead:
    fee = await service.mark_unpaid(session, fee_id)
    return FeeRead.model_validate(fee)
