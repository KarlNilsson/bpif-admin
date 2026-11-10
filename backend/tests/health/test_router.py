from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

pytestmark = pytest.mark.anyio


async def test_health_is_ok(client: AsyncClient) -> None:
    response = await client.get('/api/v1/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'database': 'ok'}


async def test_health_is_503_when_database_is_unreachable(
        app: FastAPI,
        client: AsyncClient,
        unreachable_session: AsyncSession,
) -> None:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield unreachable_session

    app.dependency_overrides[get_db] = override_get_db

    response = await client.get('/api/v1/health')

    assert response.status_code == 503
    assert response.json() == {'detail': 'Database unavailable'}
