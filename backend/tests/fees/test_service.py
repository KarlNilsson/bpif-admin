from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.fees import service
from app.fees.models import Fee, FeeStatus
from tests.factories import (create_fee, create_member,
                             create_membership_type, create_payment_request)

pytestmark = pytest.mark.anyio


async def test_mark_unpaid_clears_the_payment_and_the_link(
        db_session: AsyncSession) -> None:
    member = await create_member(db_session)
    payment_request = await create_payment_request(db_session)
    fee = await create_fee(db_session, member, status=FeeStatus.PAID,
                           payment_request_id=payment_request.id)

    result = await service.mark_unpaid(db_session, fee.id)

    assert result.status == FeeStatus.UNPAID
    assert result.paid_at is None
    assert result.payment_request_id is None
    assert result.member.id == member.id


async def test_mark_unpaid_on_an_unpaid_fee_raises(
        db_session: AsyncSession) -> None:
    fee = await create_fee(db_session, await create_member(db_session))

    with pytest.raises(ConflictError):
        await service.mark_unpaid(db_session, fee.id)


async def test_mark_unpaid_on_an_unknown_fee_raises(
        db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await service.mark_unpaid(db_session, 999999)


async def test_missing_fee_takes_the_current_type_and_amount(
        db_session: AsyncSession) -> None:
    membership_type = await create_membership_type(db_session,
                                                   amount_ore=70000)
    member = await create_member(db_session, membership_type)

    created = await service.create_missing_fees(db_session, [member.id], 2031)

    assert created == 1
    fee = await db_session.scalar(select(Fee).where(Fee.member_id == member.id))
    assert fee is not None
    assert fee.year == 2031
    assert fee.status == FeeStatus.UNPAID
    assert fee.membership_type_id == membership_type.id
    assert fee.amount_ore == 70000


async def test_existing_fee_is_not_recreated(db_session: AsyncSession) -> None:
    member = await create_member(db_session)
    await create_fee(db_session, member, year=2031)

    assert await service.create_missing_fees(
        db_session, [member.id], 2031) == 0
    assert await service.create_missing_fees(
        db_session, [member.id], 2032) == 1


@pytest.mark.parametrize('overrides', [
    pytest.param({'status': FeeStatus.PAID, 'paid_at': None},
                 id='paid without a date'),
    pytest.param({'status': FeeStatus.UNPAID,
                  'paid_at': datetime(2031, 1, 1, tzinfo=UTC)},
                 id='unpaid with a date'),
    pytest.param({'amount_ore': 0}, id='amount not positive'),
])
async def test_check_constraints(db_session: AsyncSession,
                                 overrides: dict[str, Any]) -> None:
    member = await create_member(db_session)

    with pytest.raises(IntegrityError):
        await create_fee(db_session, member, **overrides)


async def test_unpaid_fee_cannot_hold_a_link(db_session: AsyncSession) -> None:
    member = await create_member(db_session)
    payment_request = await create_payment_request(db_session)

    with pytest.raises(IntegrityError):
        await create_fee(db_session, member,
                         payment_request_id=payment_request.id)


async def test_one_fee_per_member_and_year(db_session: AsyncSession) -> None:
    member = await create_member(db_session)
    await create_fee(db_session, member, year=2031)

    with pytest.raises(IntegrityError):
        await create_fee(db_session, member, year=2031)
