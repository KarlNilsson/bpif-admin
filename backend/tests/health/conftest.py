from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

# Nothing listens on port 1, so connecting fails with an OSError.
UNREACHABLE_DATABASE_URL = 'postgresql+asyncpg://x:y@127.0.0.1:1/none'


@pytest.fixture
async def unreachable_session() -> AsyncIterator[AsyncSession]:
    """A session bound to an engine whose database can't be reached."""
    engine = create_async_engine(UNREACHABLE_DATABASE_URL, poolclass=NullPool)
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()
