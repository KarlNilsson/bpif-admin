from fastapi import APIRouter

from app.core.database import DbSession
from app.membership_types import service
from app.membership_types.schemas import MembershipTypeRead

public_router = APIRouter(prefix='/membership-types',
                          tags=['membership-types'])


@public_router.get('')
async def list_membership_types(
        session: DbSession) -> list[MembershipTypeRead]:
    membership_types = await service.list_membership_types(session)
    return [MembershipTypeRead.model_validate(membership_type)
            for membership_type in membership_types]
