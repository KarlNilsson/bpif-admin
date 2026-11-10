from pydantic import BaseModel, ConfigDict


class MembershipTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    amount_ore: int
