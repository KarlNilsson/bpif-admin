from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.fees.models import Fee
from app.fees.service import create_missing_fees, mark_member_fees_paid
from app.members.models import Member
from app.membership_types.service import get_membership_type
from app.payments.message import build_message
from app.payments.models import NAME_SEPARATOR, PaymentRequest
from app.payments.qr import build_payload
from app.payments.schemas import (LinkedFeeRead, MarkFeesPaidResult,
                                  PaymentRequestAdminRead,
                                  PaymentRequestCreate, PaymentRequestList,
                                  PaymentRequestRead)


async def create_payment_request(session: AsyncSession,
                                 data: PaymentRequestCreate,
                                 swish_number: str,
                                 year: int) -> PaymentRequest:
    membership_type = await get_membership_type(session,
                                                data.membership_type_id)

    # Can't fail for names that passed NameList, but both rules are explicit
    # preconditions of storing anything.
    build_message(data.names)
    if any(NAME_SEPARATOR in name for name in data.names):
        raise ValueError(f'A name contains {NAME_SEPARATOR!r}')

    payment_request = PaymentRequest(
        swish_number=swish_number,
        name_list=NAME_SEPARATOR.join(data.names),
        amount_ore=membership_type.amount_ore,
        year=year,
    )
    session.add(payment_request)
    await session.commit()
    return payment_request


async def get_payment_request(session: AsyncSession,
                              payment_id: UUID) -> PaymentRequest:
    payment_request = await session.get(PaymentRequest, payment_id)
    if payment_request is None:
        raise NotFoundError(f'Payment request {payment_id} not found')
    return payment_request


def to_read(payment_request: PaymentRequest) -> PaymentRequestRead:
    message = build_message(payment_request.names)
    return PaymentRequestRead(
        id=payment_request.id,
        names=payment_request.names,
        message=message,
        amount_ore=payment_request.amount_ore,
        swish_number=payment_request.swish_number,
        year=payment_request.year,
        created_at=payment_request.created_at,
        payment_url=build_payload(payment_request.swish_number,
                                  payment_request.amount_ore, message),
    )


def _to_admin_read(payment_request: PaymentRequest) -> PaymentRequestAdminRead:
    fees = sorted(payment_request.fees, key=lambda fee: fee.member.name)
    return PaymentRequestAdminRead(
        **to_read(payment_request).model_dump(),
        fees=[LinkedFeeRead.model_validate(fee) for fee in fees],
    )


async def list_payment_requests(
        session: AsyncSession,
        year: int,
        search: str | None = None,
        linked: bool | None = None) -> PaymentRequestList:
    statement = (
        select(PaymentRequest)
        .where(PaymentRequest.year == year)
        .options(selectinload(PaymentRequest.fees).selectinload(Fee.member))
        .order_by(PaymentRequest.created_at.desc(), PaymentRequest.id)
        # Fees are changed with Core UPDATEs, which loaded objects don't see.
        .execution_options(populate_existing=True)
    )
    if search:
        statement = statement.where(
            PaymentRequest.name_list.icontains(search, autoescape=True))
    if linked is True:
        statement = statement.where(PaymentRequest.fees.any())
    elif linked is False:
        statement = statement.where(~PaymentRequest.fees.any())

    result = await session.scalars(statement)
    return PaymentRequestList(
        year=year,
        items=[_to_admin_read(payment_request)
               for payment_request in result.all()],
    )


async def mark_fees_paid(session: AsyncSession, payment_id: UUID,
                         member_ids: Sequence[int]) -> MarkFeesPaidResult:
    """Links the members' fees for the request's year to the request and marks
    them paid, creating the fees that are missing. All in one transaction."""
    payment_request = await get_payment_request(session, payment_id)

    found = await session.scalars(
        select(Member.id).where(Member.id.in_(member_ids)))
    missing = set(member_ids) - set(found.all())
    if missing:
        raise NotFoundError(f'Members not found: {sorted(missing)}')

    created = await create_missing_fees(session, member_ids,
                                        payment_request.year)
    marked = await mark_member_fees_paid(session, member_ids,
                                         payment_request.year,
                                         payment_request.id)
    await session.commit()
    return MarkFeesPaidResult(marked=marked, created=created,
                              already_paid=len(member_ids) - marked)
