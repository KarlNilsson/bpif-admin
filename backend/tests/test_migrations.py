"""Checks that the models and the Alembic migrations agree."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

import app.models  # noqa: F401  (registers every domain's models)
from app.core.database import Base
from tests.conftest import alembic_config

pytestmark = pytest.mark.anyio


def _diff(connection: Connection) -> list[object]:
    context = MigrationContext.configure(connection)
    return compare_metadata(context, Base.metadata)


async def test_models_match_migrations(engine: AsyncEngine) -> None:
    # The `engine` fixture has run `alembic upgrade head` on the test
    # database. Any difference means a model changed without a migration, or
    # a migration was edited out of sync with the models.
    async with engine.connect() as connection:
        diff = await connection.run_sync(_diff)

    assert diff == []


def test_migrations_have_a_single_head() -> None:
    heads = ScriptDirectory.from_config(alembic_config()).get_heads()

    assert len(heads) <= 1, f'Diverging migration branches: {heads}'
