import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.health.service import check_database

pytestmark = pytest.mark.anyio


async def test_check_database_is_true_when_reachable(
        db_session: AsyncSession) -> None:
    assert await check_database(db_session) is True


async def test_check_database_is_false_when_unreachable(
        unreachable_session: AsyncSession) -> None:
    assert await check_database(unreachable_session) is False
