from io import BytesIO
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
import zxingcpp
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.membership_types.models import MembershipType
from app.payments.message import SWISH_MESSAGE_CHARS
from app.payments.models import PaymentRequest
from tests.conftest import TEST_SWISH_NUMBER
from tests.factories import create_member, create_payment_request

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures('current_year')]

URL = '/api/v1/payments'
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


async def type_id(session: AsyncSession, name: str = 'Junior') -> int:
    result = await session.scalar(
        select(MembershipType.id).where(MembershipType.name == name))
    assert result is not None
    return result


async def post_names(client: AsyncClient, session: AsyncSession,
                     names: list[str]) -> Any:
    return await client.post(URL, json={
        'names': names,
        'membership_type_id': await type_id(session),
    })


def decode_png(png: bytes) -> str:
    image = Image.open(BytesIO(png)).convert('L')
    results = zxingcpp.read_barcodes(image)
    assert len(results) == 1
    return results[0].text


async def test_create_payment_request(client: AsyncClient,
                                      db_session: AsyncSession) -> None:
    response = await post_names(client, db_session, ['Anna Svensson'])

    assert response.status_code == 201
    body = response.json()
    UUID(body['id'])
    assert body['names'] == ['Anna Svensson']
    assert body['amount_ore'] == 30000
    assert body['swish_number'] == TEST_SWISH_NUMBER
    assert body['year'] == 2031
    assert body['message'] == 'Medlemskap Anna Svensson'
    assert body['payment_url'].startswith('https://app.swish.nu/1/p/sw/')


@pytest.mark.parametrize(('field', 'value'), [
    ('amount', 1),
    ('amount_ore', 1),
    ('message', 'Hej'),
    ('swish_number', '1239999999'),
])
async def test_extra_fields_are_rejected(client: AsyncClient,
                                         db_session: AsyncSession,
                                         field: str, value: object) -> None:
    response = await client.post(URL, json={
        'names': ['Anna Ek'],
        'membership_type_id': await type_id(db_session),
        field: value,
    })

    assert response.status_code == 422


@pytest.mark.parametrize('names', [
    [],
    ['Anna Ek'] * 11,
    ['😀'],
    ['123'],
    ['Иван Петров'],
    ['A' * 61],
])
async def test_invalid_names_are_rejected(client: AsyncClient,
                                          db_session: AsyncSession,
                                          names: list[str]) -> None:
    response = await post_names(client, db_session, names)

    assert response.status_code == 422


async def test_missing_membership_type_is_rejected(
        client: AsyncClient) -> None:
    response = await client.post(URL, json={'names': ['Anna Ek']})

    assert response.status_code == 422


async def test_unknown_membership_type_is_404(client: AsyncClient) -> None:
    response = await client.post(URL, json={
        'names': ['Anna Ek'], 'membership_type_id': 999999})

    assert response.status_code == 404


async def test_markup_is_removed_before_storing(
        client: AsyncClient, db_session: AsyncSession) -> None:
    response = await post_names(client, db_session,
                                ['<script>alert(1)</script> Anna'])

    assert response.status_code == 201
    stored = await db_session.get(PaymentRequest, UUID(response.json()['id']))
    assert stored is not None
    assert stored.name_list == 'scriptalertscript Anna'


async def test_invisible_characters_are_removed(
        client: AsyncClient, db_session: AsyncSession) -> None:
    response = await post_names(client, db_session,
                                ['An​na‮ Ek'])

    assert response.status_code == 201
    assert response.json()['names'] == ['Anna Ek']


async def test_worst_case_names_fit_the_swish_message(
        client: AsyncClient, db_session: AsyncSession) -> None:
    long_name = 'Ab Cd Ef ' + 'G' * 51
    assert len(long_name) == 60

    response = await post_names(client, db_session, [long_name] * 10)

    assert response.status_code == 201
    body = response.json()
    assert len(body['message']) <= 50
    assert set(body['message']) <= SWISH_MESSAGE_CHARS

    qr = await client.get(f'{URL}/{body["id"]}/qr.png')
    query = parse_qs(urlsplit(decode_png(qr.content)).query)
    assert query['msg'] == [body['message']]


async def test_get_payment_request(client: AsyncClient,
                                   db_session: AsyncSession) -> None:
    created = (await post_names(client, db_session, ['Anna Ek'])).json()

    response = await client.get(f'{URL}/{created["id"]}')

    assert response.status_code == 200
    assert response.json() == created


async def test_get_unknown_payment_request_is_404(
        client: AsyncClient) -> None:
    response = await client.get(f'{URL}/{uuid4()}')

    assert response.status_code == 404


async def test_get_malformed_id_is_422(client: AsyncClient) -> None:
    response = await client.get(f'{URL}/abc')

    assert response.status_code == 422


async def test_qr_code(client: AsyncClient, db_session: AsyncSession) -> None:
    created = (await post_names(client, db_session, ['Åsa Öberg'])).json()

    response = await client.get(f'{URL}/{created["id"]}/qr.png')

    assert response.status_code == 200
    assert response.headers['content-type'] == 'image/png'
    assert response.headers['cache-control'] == 'private, max-age=86400'
    assert response.content.startswith(PNG_SIGNATURE)

    payload = decode_png(response.content)
    assert payload == created['payment_url']
    assert len(parse_qs(urlsplit(payload).query)['msg'][0]) <= 50


async def test_qr_code_for_unknown_id_is_404(client: AsyncClient) -> None:
    response = await client.get(f'{URL}/{uuid4()}/qr.png')

    assert response.status_code == 404


async def test_list_defaults_to_the_current_year(
        client: AsyncClient, db_session: AsyncSession) -> None:
    current = await create_payment_request(db_session, year=2031)
    await create_payment_request(db_session, year=2030)

    response = await client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert body['year'] == 2031
    assert [item['id'] for item in body['items']] == [str(current.id)]
    assert body['items'][0]['fees'] == []


async def test_list_takes_year_search_and_linked(
        client: AsyncClient, db_session: AsyncSession) -> None:
    await create_payment_request(db_session, year=2030, name_list='Anna Ek')

    response = await client.get(URL, params={
        'year': 2030, 'search': 'anna', 'linked': 'false'})
    assert len(response.json()['items']) == 1

    response = await client.get(URL, params={'year': 2030, 'linked': 'true'})
    assert response.json()['items'] == []


async def test_list_rejects_an_invalid_year(client: AsyncClient) -> None:
    response = await client.get(URL, params={'year': 1999})

    assert response.status_code == 422


async def test_mark_fees_paid(client: AsyncClient,
                              db_session: AsyncSession) -> None:
    member = await create_member(db_session, name='Anna Ek')
    payment_request = await create_payment_request(db_session, year=2031)

    response = await client.post(
        f'{URL}/{payment_request.id}/mark-fees-paid',
        json={'member_ids': [member.id, member.id]})

    assert response.status_code == 200
    assert response.json() == {'marked': 1, 'created': 1, 'already_paid': 0}

    listed = (await client.get(URL)).json()
    fees = listed['items'][0]['fees']
    assert [fee['member']['name'] for fee in fees] == ['Anna Ek']
    assert fees[0]['paid_at'] is not None


async def test_mark_fees_paid_with_unknown_member_is_404(
        client: AsyncClient, db_session: AsyncSession) -> None:
    payment_request = await create_payment_request(db_session)

    response = await client.post(
        f'{URL}/{payment_request.id}/mark-fees-paid',
        json={'member_ids': [999999]})

    assert response.status_code == 404


async def test_mark_fees_paid_on_unknown_request_is_404(
        client: AsyncClient, db_session: AsyncSession) -> None:
    member = await create_member(db_session)

    response = await client.post(f'{URL}/{uuid4()}/mark-fees-paid',
                                 json={'member_ids': [member.id]})

    assert response.status_code == 404


@pytest.mark.parametrize('body', [
    {'member_ids': []},
    {'member_ids': list(range(1, 22))},
    {},
    {'member_ids': [1], 'year': 2031},
])
async def test_mark_fees_paid_rejects_invalid_bodies(
        client: AsyncClient, db_session: AsyncSession,
        body: dict[str, object]) -> None:
    payment_request = await create_payment_request(db_session)

    response = await client.post(
        f'{URL}/{payment_request.id}/mark-fees-paid', json=body)

    assert response.status_code == 422
