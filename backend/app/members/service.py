from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.members.models import Member
from app.members.schemas import MemberCreate
from app.membership_types.service import get_membership_type


async def list_members(session: AsyncSession,
                       search: str | None = None) -> Sequence[Member]:
    statement = (
        select(Member)
        .options(selectinload(Member.membership_type))
        .order_by(Member.name, Member.member_number)
    )
    if search:
        statement = statement.where(or_(
            Member.name.icontains(search, autoescape=True),
            Member.member_number.istartswith(search, autoescape=True),
        ))
    result = await session.scalars(statement)
    return result.all()


async def get_member(session: AsyncSession, member_id: int) -> Member:
    member = await session.scalar(
        select(Member)
        .where(Member.id == member_id)
        .options(selectinload(Member.membership_type))
    )
    if member is None:
        raise NotFoundError(f'Member {member_id} not found')
    return member


async def create_member(session: AsyncSession, data: MemberCreate) -> Member:
    await get_membership_type(session, data.membership_type_id)

    conflict = ConflictError(
        f'Member number {data.member_number} is already in use')
    existing = await session.scalar(
        select(Member.id).where(Member.member_number == data.member_number))
    if existing is not None:
        raise conflict

    member = Member(**data.model_dump())
    session.add(member)
    try:
        await session.commit()
    except IntegrityError:
        # Lost a race with another request for the same number.
        await session.rollback()
        raise conflict
    return await get_member(session, member.id)
