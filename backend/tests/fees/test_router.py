import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.fees.models import FeeStatus
from tests.factories import (create_fee, create_member,
                             create_payment_request)

pytestmark = pytest.mark.anyio


async def test_mark_unpaid(client: AsyncClient,
                           db_session: AsyncSession) -> None:
    member = await create_member(db_session, name='Anna Ek')
    payment_request = await create_payment_request(db_session)
    fee = await create_fee(db_session, member, status=FeeStatus.PAID,
                           payment_request_id=payment_request.id)

    response = await client.post(f'/api/v1/fees/{fee.id}/mark-unpaid')

    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'unpaid'
    assert body['paid_at'] is None
    assert body['payment_request_id'] is None
    assert body['member']['name'] == 'Anna Ek'


async def test_mark_unpaid_twice_is_409(client: AsyncClient,
                                        db_session: AsyncSession) -> None:
    fee = await create_fee(db_session, await create_member(db_session))

    response = await client.post(f'/api/v1/fees/{fee.id}/mark-unpaid')

    assert response.status_code == 409


async def test_mark_unpaid_on_unknown_fee_is_404(client: AsyncClient) -> None:
    response = await client.post('/api/v1/fees/999999/mark-unpaid')

    assert response.status_code == 404
