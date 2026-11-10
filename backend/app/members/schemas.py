from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.membership_types.schemas import MembershipTypeRead
from app.payments.schemas import Name

MemberNumber = Annotated[str, StringConstraints(
    strip_whitespace=True, pattern=r'^[A-Za-z0-9-]{1,20}$')]


class MemberCreate(BaseModel):
    member_number: MemberNumber
    name: Name
    membership_type_id: int


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    member_number: str
    name: str
    membership_type: MembershipTypeRead
