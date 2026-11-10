from fastapi import APIRouter, status

from app.core.database import DbSession
from app.members import service
from app.members.schemas import MemberCreate, MemberRead

admin_router = APIRouter(prefix='/members', tags=['members'])


@admin_router.get('')
async def list_members(session: DbSession,
                       search: str | None = None) -> list[MemberRead]:
    members = await service.list_members(session, search)
    return [MemberRead.model_validate(member) for member in members]


@admin_router.post('', status_code=status.HTTP_201_CREATED)
async def create_member(data: MemberCreate, session: DbSession) -> MemberRead:
    member = await service.create_member(session, data)
    return MemberRead.model_validate(member)
