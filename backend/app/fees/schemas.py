from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.fees.models import FeeStatus


class FeeMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    member_number: str
    name: str


class FeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    status: FeeStatus
    amount_ore: int
    paid_at: datetime | None
    payment_request_id: UUID | None
    member: FeeMemberRead
