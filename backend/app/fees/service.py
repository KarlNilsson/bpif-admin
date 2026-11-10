from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.fees.models import Fee, FeeStatus
from app.members.models import Member
from app.membership_types.models import MembershipType


async def get_fee(session: AsyncSession, fee_id: int) -> Fee:
    fee = await session.scalar(
        select(Fee)
        .where(Fee.id == fee_id)
        .options(selectinload(Fee.member))
        # A Core UPDATE in the same session would otherwise leave it stale.
        .execution_options(populate_existing=True)
    )
    if fee is None:
        raise NotFoundError(f'Fee {fee_id} not found')
    return fee


async def create_missing_fees(session: AsyncSession,
                              member_ids: Sequence[int], year: int) -> int:
    """Creates the fees that don't exist yet, using each member's current type
    and its amount. Joins the caller's transaction and doesn't commit."""
    result = await session.scalars(
        insert(Fee)
        .from_select(
            ['member_id', 'year', 'membership_type_id', 'amount_ore',
             'status'],
            select(Member.id, literal(year), Member.membership_type_id,
                   MembershipType.amount_ore,
                   literal(FeeStatus.UNPAID.value))
            .join(Member.membership_type)
            .where(Member.id.in_(member_ids)),
        )
        .on_conflict_do_nothing(index_elements=['member_id', 'year'])
        .returning(Fee.id)
    )
    return len(result.all())


async def mark_member_fees_paid(session: AsyncSession,
                                member_ids: Sequence[int], year: int,
                                payment_request_id: UUID) -> int:
    """Marks the members' unpaid fees as paid through a payment request. Fees
    that are already paid keep their original request. Joins the caller's
    transaction and doesn't commit."""
    result = await session.scalars(
        update(Fee)
        .where(Fee.member_id.in_(member_ids),
               Fee.year == year,
               Fee.status == FeeStatus.UNPAID)
        .values(status=FeeStatus.PAID, paid_at=func.now(),
                payment_request_id=payment_request_id)
        .returning(Fee.id)
    )
    return len(result.all())


async def mark_unpaid(session: AsyncSession, fee_id: int) -> Fee:
    result = await session.execute(
        update(Fee)
        .where(Fee.id == fee_id, Fee.status == FeeStatus.PAID)
        .values(status=FeeStatus.UNPAID, paid_at=None,
                payment_request_id=None)
        .returning(Fee.id)
    )
    if result.scalar_one_or_none() is None:
        # Raises NotFoundError when the fee doesn't exist.
        await get_fee(session, fee_id)
        raise ConflictError('Fee is not paid')

    await session.commit()
    return await get_fee(session, fee_id)
