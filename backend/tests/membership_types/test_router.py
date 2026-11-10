import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_list_membership_types_is_public(client: AsyncClient) -> None:
    response = await client.get('/api/v1/membership-types')

    assert response.status_code == 200
    junior = next(t for t in response.json() if t['name'] == 'Junior')
    assert junior == {'id': junior['id'], 'name': 'Junior',
                      'amount_ore': 30000}
