from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.membership_types.models import MembershipType


async def list_membership_types(
        session: AsyncSession) -> Sequence[MembershipType]:
    result = await session.scalars(
        select(MembershipType).order_by(MembershipType.amount_ore,
                                        MembershipType.name))
    return result.all()


async def get_membership_type(session: AsyncSession,
                              type_id: int) -> MembershipType:
    membership_type = await session.get(MembershipType, type_id)
    if membership_type is None:
        raise NotFoundError(f'Membership type {type_id} not found')
    return membership_type
