import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.members import service
from app.members.schemas import MemberCreate
from tests.factories import create_member, create_membership_type

pytestmark = pytest.mark.anyio


async def test_create_loads_the_membership_type(
        db_session: AsyncSession) -> None:
    membership_type = await create_membership_type(db_session)

    member = await service.create_member(db_session, MemberCreate(
        member_number='A-1', name='Anna Ek',
        membership_type_id=membership_type.id))

    assert member.membership_type.id == membership_type.id


async def test_create_with_unknown_type_raises(
        db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await service.create_member(db_session, MemberCreate(
            member_number='A-1', name='Anna Ek', membership_type_id=999999))


async def test_duplicate_member_number_raises(
        db_session: AsyncSession) -> None:
    existing = await create_member(db_session)

    with pytest.raises(ConflictError):
        await service.create_member(db_session, MemberCreate(
            member_number=existing.member_number, name='Anna Ek',
            membership_type_id=existing.membership_type_id))


async def test_search_finds_a_name_substring_in_any_case(
        db_session: AsyncSession) -> None:
    anna = await create_member(db_session, name='Anna Svensson')
    await create_member(db_session, name='Erik Berg')

    found = await service.list_members(db_session, 'SVENS')

    assert [m.id for m in found] == [anna.id]


async def test_search_finds_a_member_number_prefix(
        db_session: AsyncSession) -> None:
    member = await create_member(db_session, member_number='XY-1')
    await create_member(db_session, member_number='1-XY')

    found = await service.list_members(db_session, 'xy')

    assert [m.id for m in found] == [member.id]


@pytest.mark.parametrize('search', ['%', '_'])
async def test_search_treats_wildcards_literally(db_session: AsyncSession,
                                                 search: str) -> None:
    await create_member(db_session, name='Anna Ek')

    assert await service.list_members(db_session, search) == []


async def test_list_is_ordered_by_name(db_session: AsyncSession) -> None:
    erik = await create_member(db_session, name='Erik Berg')
    anna = await create_member(db_session, name='Anna Ek')

    found = await service.list_members(db_session)

    assert [m.id for m in found] == [anna.id, erik.id]
