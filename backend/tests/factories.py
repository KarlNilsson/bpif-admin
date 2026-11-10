"""Helpers that add rows to the test session and flush.

Defaults are unique per call, so tests don't collide.
"""

from datetime import UTC, datetime
from itertools import count
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.fees.models import Fee, FeeStatus
from app.members.models import Member
from app.membership_types.models import MembershipType
from app.payments.models import PaymentRequest

_counter = count(1)


async def create_membership_type(session: AsyncSession,
                                 **overrides: Any) -> MembershipType:
    values: dict[str, Any] = {
        'name': f'Typ {next(_counter)}',
        'amount_ore': 30000,
    }
    membership_type = MembershipType(**(values | overrides))
    session.add(membership_type)
    await session.flush()
    return membership_type


async def create_member(session: AsyncSession,
                        membership_type: MembershipType | None = None,
                        **overrides: Any) -> Member:
    if membership_type is None:
        membership_type = await create_membership_type(session)
    number = next(_counter)
    values: dict[str, Any] = {
        'member_number': f'M{number}',
        'name': f'Medlem {number}',
        'membership_type_id': membership_type.id,
    }
    member = Member(**(values | overrides))
    session.add(member)
    await session.flush()
    return member


async def create_payment_request(session: AsyncSession,
                                 **overrides: Any) -> PaymentRequest:
    values: dict[str, Any] = {
        'swish_number': '1231234567',
        'name_list': 'Anna Ek',
        'amount_ore': 30000,
        'year': 2031,
    }
    payment_request = PaymentRequest(**(values | overrides))
    session.add(payment_request)
    await session.flush()
    return payment_request


async def create_fee(session: AsyncSession, member: Member, year: int = 2031,
                     status: FeeStatus = FeeStatus.UNPAID,
                     **overrides: Any) -> Fee:
    values: dict[str, Any] = {
        'member_id': member.id,
        'year': year,
        'membership_type_id': member.membership_type_id,
        'amount_ore': 30000,
        'status': status,
        'paid_at': datetime.now(UTC) if status == FeeStatus.PAID else None,
    }
    fee = Fee(**(values | overrides))
    session.add(fee)
    await session.flush()
    return fee
