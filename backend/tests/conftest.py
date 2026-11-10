"""Shared fixtures for the backend tests.

Database tests run against a dedicated PostgreSQL test database, given by
`TEST_DATABASE_URL`. It is dropped and recreated on every pytest session, and
the schema is created by running the Alembic migrations. Each test runs in an
outer transaction that is rolled back afterwards.

The fixtures that need the database are only set up when a test requests
them, so pure unit tests (e.g. `tests/payments/`) run without any database or
environment variables.
"""

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    create_async_engine)
from sqlalchemy.pool import NullPool

# Models refer to each other across domains, so they must be registered
# together even when only one domain's tests run. Not `import app.models`,
# because the `app` fixture has the same name.
from app import models  # noqa: F401

BACKEND_ROOT = Path(__file__).parents[1]
ALEMBIC_INI = BACKEND_ROOT / 'alembic.ini'
TEST_DATABASE_SUFFIX = '_test'
TEST_SWISH_NUMBER = '1239999999'


def alembic_config() -> Config:
    """Alembic config resolved from the backend root, so pytest works from
    any working directory."""
    return Config(str(ALEMBIC_INI))


def get_test_database_url() -> str:
    """Reads TEST_DATABASE_URL and refuses anything that could be the
    development database."""
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.fail(
            'TEST_DATABASE_URL is not set. Database tests need a dedicated '
            'test database (see .env.example).',
            pytrace=False,
        )
    if url == os.environ.get('DATABASE_URL'):
        pytest.fail(
            'TEST_DATABASE_URL equals DATABASE_URL. Refusing to run the tests '
            'against the application database.',
            pytrace=False,
        )
    database = make_url(url).database
    if not database or not database.endswith(TEST_DATABASE_SUFFIX):
        pytest.fail(
            f'The test database name must end in {TEST_DATABASE_SUFFIX!r} '
            f'(got {database!r}). Refusing to drop and recreate it.',
            pytrace=False,
        )
    return url


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


async def recreate_database(url: str) -> None:
    """Drops and creates the database in `url`, connecting through the
    `postgres` maintenance database on the same server."""
    database = quote_identifier(make_url(url).database or '')
    maintenance_url = make_url(url).set(database='postgres')
    engine = create_async_engine(
        maintenance_url, isolation_level='AUTOCOMMIT', poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text(f'DROP DATABASE IF EXISTS {database} WITH (FORCE)'))
            await connection.execute(text(f'CREATE DATABASE {database}'))
    finally:
        await engine.dispose()


def _upgrade(connection: Connection) -> None:
    cfg = alembic_config()
    cfg.attributes['connection'] = connection
    command.upgrade(cfg, 'head')


@pytest.fixture(scope='session')
def anyio_backend() -> str:
    # Session scope lets the session-scoped async `engine` fixture share the
    # event loop with the tests.
    return 'asyncio'


@pytest.fixture(scope='session')
async def engine() -> AsyncIterator[AsyncEngine]:
    url = get_test_database_url()
    await recreate_database(url)

    # NullPool avoids connections leaking between event loops.
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(_upgrade)

    yield engine

    # The database is left in place for inspection and dropped by the next
    # run.
    await engine.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session inside an outer transaction that is rolled back afterwards.

    With `create_savepoint`, a service's `commit()` only releases a savepoint
    and its `rollback()` rolls back to it, so the outer rollback still undoes
    everything.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode='create_savepoint',
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    # Imported lazily: `app.main` builds the app at import time, which needs
    # DATABASE_URL. Pure unit tests never import it.
    from app.core.config import Settings, get_settings
    from app.core.database import get_db
    from app.main import create_app

    app = create_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    # ASGITransport doesn't run the lifespan, so every database access in
    # tests goes through this override.
    app.dependency_overrides[get_db] = override_get_db
    # Pins the value for endpoints. `create_app` reads the real settings when
    # `app.main` is imported, so SWISH_NUMBER must be set in the environment
    # too.
    app.dependency_overrides[get_settings] = lambda: Settings(
        swish_number=TEST_SWISH_NUMBER)
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as c:
        yield c
