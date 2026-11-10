from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import (ConflictError, DomainError, NotFoundError,
                                 register_exception_handlers)

pytestmark = pytest.mark.anyio


def build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get('/not-found')
    async def not_found() -> None:
        raise NotFoundError('x')

    @app.get('/conflict')
    async def conflict() -> None:
        raise ConflictError('y')

    @app.get('/domain-error')
    async def domain_error() -> None:
        raise DomainError('z')

    return app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=build_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url='http://test') as c:
        yield c


@pytest.mark.parametrize(('path', 'status_code', 'detail'), [
    ('/not-found', 404, 'x'),
    ('/conflict', 409, 'y'),
])
async def test_domain_errors_are_mapped_to_status_codes(
        client: AsyncClient, path: str, status_code: int, detail: str) -> None:
    response = await client.get(path)

    assert response.status_code == status_code
    assert response.json() == {'detail': detail}


async def test_bare_domain_error_is_a_server_error(
        client: AsyncClient) -> None:
    response = await client.get('/domain-error')

    assert response.status_code == 500


def test_message_is_kept() -> None:
    error = NotFoundError('Member 3 not found')

    assert error.message == 'Member 3 not found'
    assert str(error) == 'Member 3 not found'
