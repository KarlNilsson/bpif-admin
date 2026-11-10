import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.membership_types import service
from tests.factories import create_membership_type

pytestmark = pytest.mark.anyio


async def test_seeded_types(db_session: AsyncSession) -> None:
    types = await service.list_membership_types(db_session)

    assert {t.name: t.amount_ore for t in types} == {
        'Junior': 30000,
        'Senior': 50000,
        'Familj': 70000,
        'Stödmedlem': 30000,
    }


async def test_list_is_ordered_by_amount_then_name(
        db_session: AsyncSession) -> None:
    types = await service.list_membership_types(db_session)

    assert [t.name for t in types] == [
        'Junior', 'Stödmedlem', 'Senior', 'Familj']


async def test_get_membership_type(db_session: AsyncSession) -> None:
    created = await create_membership_type(db_session)

    assert await service.get_membership_type(db_session, created.id) is created


async def test_get_unknown_type_raises(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await service.get_membership_type(db_session, 999999)
