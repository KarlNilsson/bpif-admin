from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.fees.models import Fee, FeeStatus
from app.fees.service import mark_unpaid
from app.members.models import Member
from app.membership_types.models import MembershipType
from app.payments import service
from app.payments.message import build_message
from app.payments.models import PaymentRequest
from app.payments.qr import build_payload
from app.payments.schemas import MarkFeesPaidResult, PaymentRequestCreate
from tests.factories import (create_fee, create_member,
                             create_membership_type, create_payment_request)

pytestmark = pytest.mark.anyio

SWISH_NUMBER = '1231234567'
YEAR = 2031


async def type_id(session: AsyncSession, name: str) -> int:
    result = await session.scalar(
        select(MembershipType.id).where(MembershipType.name == name))
    assert result is not None
    return result


async def create(session: AsyncSession, type_name: str,
                 names: list[str]) -> PaymentRequest:
    data = PaymentRequestCreate(
        names=names, membership_type_id=await type_id(session, type_name))
    return await service.create_payment_request(session, data, SWISH_NUMBER,
                                                YEAR)


async def fee_of(session: AsyncSession, member: Member) -> Fee:
    fee = await session.scalar(
        select(Fee)
        .where(Fee.member_id == member.id)
        .execution_options(populate_existing=True))
    assert fee is not None
    return fee


@pytest.mark.parametrize(('type_name', 'names', 'amount_ore'), [
    ('Junior', ['Anna Svensson'], 30000),
    ('Senior', ['Erik Berg'], 50000),
    ('Familj', ['Anna Svensson', 'Erik Svensson'], 70000),
    ('Stödmedlem', ['Lisa Ek'], 30000),
])
async def test_amount_comes_from_the_membership_type(
        db_session: AsyncSession, type_name: str, names: list[str],
        amount_ore: int) -> None:
    payment_request = await create(db_session, type_name, names)

    assert payment_request.amount_ore == amount_ore


async def test_amount_is_per_request_not_per_name(
        db_session: AsyncSession) -> None:
    payment_request = await create(db_session, 'Junior',
                                   ['Anna Ek', 'Erik Ek', 'Lisa Ek'])

    assert payment_request.amount_ore == 30000


async def test_unknown_type_raises_and_stores_nothing(
        db_session: AsyncSession) -> None:
    data = PaymentRequestCreate(names=['Anna Ek'], membership_type_id=999999)

    with pytest.raises(NotFoundError):
        await service.create_payment_request(db_session, data, SWISH_NUMBER,
                                             YEAR)

    count = await db_session.scalar(
        select(func.count()).select_from(PaymentRequest))
    assert count == 0


async def test_stores_the_sanitised_names_and_the_given_values(
        db_session: AsyncSession) -> None:
    payment_request = await create(db_session, 'Junior',
                                   ['  Åsa   Öberg ', 'José Müller 😀'])

    # Original letters are kept. Folding only happens in the message.
    assert payment_request.name_list == 'Åsa Öberg;José Müller'
    assert payment_request.names == ['Åsa Öberg', 'José Müller']
    assert payment_request.swish_number == SWISH_NUMBER
    assert payment_request.year == YEAR
    assert payment_request.created_at is not None


async def test_get_payment_request(db_session: AsyncSession) -> None:
    created = await create(db_session, 'Junior', ['Anna Ek'])

    found = await service.get_payment_request(db_session, created.id)

    assert found is created


async def test_to_read_derives_the_message_and_link(
        db_session: AsyncSession) -> None:
    payment_request = await create(db_session, 'Junior', ['Anna Ek'])

    read = service.to_read(payment_request)

    assert read.message == build_message(['Anna Ek'])
    assert read.payment_url == build_payload(SWISH_NUMBER, 30000, read.message)


async def test_creating_a_request_links_nothing(
        db_session: AsyncSession) -> None:
    member = await create_member(db_session, name='Anna Ek')
    await create_fee(db_session, member)

    payment_request = await create(db_session, 'Junior', ['Anna Ek'])

    assert (await fee_of(db_session, member)).payment_request_id is None
    listed = await service.list_payment_requests(db_session, YEAR)
    assert [item.id for item in listed.items] == [payment_request.id]
    assert listed.items[0].fees == []


async def test_mark_fees_paid(db_session: AsyncSession) -> None:
    membership_type = await create_membership_type(db_session,
                                                   amount_ore=50000)
    unpaid = await create_member(db_session, membership_type)
    paid = await create_member(db_session, membership_type)
    no_fee = await create_member(db_session, membership_type)
    await create_fee(db_session, unpaid, year=YEAR)
    earlier = await create_payment_request(db_session, year=YEAR)
    await create_fee(db_session, paid, year=YEAR, status=FeeStatus.PAID,
                     payment_request_id=earlier.id)
    payment_request = await create_payment_request(db_session, year=YEAR)
    member_ids = [unpaid.id, paid.id, no_fee.id]

    result = await service.mark_fees_paid(db_session, payment_request.id,
                                          member_ids)

    assert result == MarkFeesPaidResult(marked=2, created=1, already_paid=1)

    unpaid_fee = await fee_of(db_session, unpaid)
    assert unpaid_fee.status == FeeStatus.PAID
    assert unpaid_fee.paid_at is not None
    assert unpaid_fee.payment_request_id == payment_request.id

    assert (await fee_of(db_session, paid)).payment_request_id == earlier.id

    new_fee = await fee_of(db_session, no_fee)
    assert new_fee.status == FeeStatus.PAID
    assert new_fee.year == YEAR
    assert new_fee.amount_ore == 50000
    assert new_fee.membership_type_id == membership_type.id
    assert new_fee.payment_request_id == payment_request.id

    again = await service.mark_fees_paid(db_session, payment_request.id,
                                         member_ids)
    assert again == MarkFeesPaidResult(marked=0, created=0, already_paid=3)


async def test_family_payment_gives_one_fee_per_member(
        db_session: AsyncSession) -> None:
    familj = await db_session.scalar(
        select(MembershipType).where(MembershipType.name == 'Familj'))
    anna = await create_member(db_session, familj, name='Anna Ek')
    erik = await create_member(db_session, familj, name='Erik Ek')
    payment_request = await create(db_session, 'Familj',
                                   ['Anna Ek', 'Erik Ek'])

    await service.mark_fees_paid(db_session, payment_request.id,
                                 [anna.id, erik.id])

    for member in (anna, erik):
        fee = await fee_of(db_session, member)
        assert fee.payment_request_id == payment_request.id
        assert fee.amount_ore == 70000


async def test_changing_the_type_amount_keeps_the_fee_snapshot(
        db_session: AsyncSession) -> None:
    membership_type = await create_membership_type(db_session,
                                                   amount_ore=30000)
    member = await create_member(db_session, membership_type)
    payment_request = await create_payment_request(db_session)
    await service.mark_fees_paid(db_session, payment_request.id, [member.id])

    membership_type.amount_ore = 99900
    await db_session.flush()

    assert (await fee_of(db_session, member)).amount_ore == 30000


async def test_unknown_member_changes_nothing(
        db_session: AsyncSession) -> None:
    member = await create_member(db_session)
    payment_request = await create_payment_request(db_session)

    with pytest.raises(NotFoundError, match='999999'):
        await service.mark_fees_paid(db_session, payment_request.id,
                                     [member.id, 999999])

    count = await db_session.scalar(select(func.count()).select_from(Fee))
    assert count == 0


async def test_unknown_request_raises(db_session: AsyncSession) -> None:
    member = await create_member(db_session)

    with pytest.raises(NotFoundError):
        await service.mark_fees_paid(db_session, uuid4(), [member.id])


async def test_undoing_the_last_fee_unlinks_the_request(
        db_session: AsyncSession) -> None:
    anna = await create_member(db_session)
    erik = await create_member(db_session)
    payment_request = await create_payment_request(db_session, year=YEAR)
    await service.mark_fees_paid(db_session, payment_request.id,
                                 [anna.id, erik.id])

    await mark_unpaid(db_session, (await fee_of(db_session, anna)).id)
    linked = await service.list_payment_requests(db_session, YEAR, linked=True)
    assert [fee.member.id for fee in linked.items[0].fees] == [erik.id]

    await mark_unpaid(db_session, (await fee_of(db_session, erik)).id)
    linked = await service.list_payment_requests(db_session, YEAR, linked=True)
    assert linked.items == []
    unlinked = await service.list_payment_requests(db_session, YEAR,
                                                   linked=False)
    assert [item.id for item in unlinked.items] == [payment_request.id]


async def test_list_filters_by_year(db_session: AsyncSession) -> None:
    current = await create_payment_request(db_session, year=YEAR)
    await create_payment_request(db_session, year=YEAR - 1)

    listed = await service.list_payment_requests(db_session, YEAR)

    assert listed.year == YEAR
    assert [item.id for item in listed.items] == [current.id]


async def test_list_searches_names(db_session: AsyncSession) -> None:
    anna = await create_payment_request(db_session,
                                        name_list='Anna Ek;Erik Ek')
    await create_payment_request(db_session, name_list='Lisa Berg')

    listed = await service.list_payment_requests(db_session, YEAR,
                                                 search='ERIK')
    assert [item.id for item in listed.items] == [anna.id]

    listed = await service.list_payment_requests(db_session, YEAR, search='%')
    assert listed.items == []


async def test_list_is_newest_first(db_session: AsyncSession) -> None:
    older = await create_payment_request(
        db_session, created_at=datetime(2031, 1, 1, tzinfo=UTC))
    newer = await create_payment_request(
        db_session, created_at=datetime(2031, 2, 1, tzinfo=UTC))

    listed = await service.list_payment_requests(db_session, YEAR)

    assert [item.id for item in listed.items] == [newer.id, older.id]


async def test_list_orders_linked_fees_by_member_name(
        db_session: AsyncSession) -> None:
    erik = await create_member(db_session, name='Erik Ek')
    anna = await create_member(db_session, name='Anna Ek')
    payment_request = await create_payment_request(db_session)
    await service.mark_fees_paid(db_session, payment_request.id,
                                 [erik.id, anna.id])

    listed = await service.list_payment_requests(db_session, YEAR)

    assert [fee.member.name for fee in listed.items[0].fees] == [
        'Anna Ek', 'Erik Ek']
