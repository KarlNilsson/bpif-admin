import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import create_member, create_membership_type

pytestmark = pytest.mark.anyio

URL = '/api/v1/members'


async def test_create_member(client: AsyncClient,
                             db_session: AsyncSession) -> None:
    membership_type = await create_membership_type(db_session)

    response = await client.post(URL, json={
        'member_number': 'A-1',
        'name': 'Anna Ek',
        'membership_type_id': membership_type.id,
    })

    assert response.status_code == 201
    body = response.json()
    assert body['name'] == 'Anna Ek'
    assert body['membership_type']['id'] == membership_type.id


async def test_duplicate_member_number_is_409(
        client: AsyncClient, db_session: AsyncSession) -> None:
    existing = await create_member(db_session)

    response = await client.post(URL, json={
        'member_number': existing.member_number,
        'name': 'Anna Ek',
        'membership_type_id': existing.membership_type_id,
    })

    assert response.status_code == 409


async def test_unknown_membership_type_is_404(client: AsyncClient) -> None:
    response = await client.post(URL, json={
        'member_number': 'A-1', 'name': 'Anna Ek',
        'membership_type_id': 999999})

    assert response.status_code == 404


async def test_invalid_name_is_422(client: AsyncClient) -> None:
    response = await client.post(URL, json={
        'member_number': 'A-1', 'name': '123', 'membership_type_id': 1})

    assert response.status_code == 422


async def test_search_members(client: AsyncClient,
                              db_session: AsyncSession) -> None:
    anna = await create_member(db_session, name='Anna Ek')
    await create_member(db_session, name='Erik Berg')

    response = await client.get(URL, params={'search': 'anna'})

    assert response.status_code == 200
    assert [m['id'] for m in response.json()] == [anna.id]
