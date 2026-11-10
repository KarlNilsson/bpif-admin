import re
import unicodedata
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (AfterValidator, BaseModel, ConfigDict, Field,
                      PositiveInt, StringConstraints)

from app.payments.message import to_swish_text

# app.core.config imports this module, so it must not import anything that
# depends on the settings, such as the models.

# Chosen so the message always fits in initials form, see
# app.payments.message.build_message.
MAX_NAMES = 10
MAX_NAME_LENGTH = 60

QUOTE_MAP = {'’': "'", '‘': "'"}


def _keep_char(char: str) -> bool:
    return unicodedata.category(char)[0] in ('L', 'M') or char in " -'"


def sanitize_name(value: str) -> str:
    """Normalises a name, keeping only letters, spaces, '-' and "'"."""
    value = unicodedata.normalize('NFC', value)
    value = ''.join(' ' if c.isspace() else QUOTE_MAP.get(c, c)
                    for c in value)
    value = ''.join(c for c in value if _keep_char(c))
    value = re.sub(' +', ' ', value).strip()

    if not any(c.isalpha() for c in value):
        raise ValueError('Name must contain at least one letter')
    if len(value) > MAX_NAME_LENGTH:
        raise ValueError(
            f'Name must be at most {MAX_NAME_LENGTH} characters')
    if not any(c.isalpha() for c in to_swish_text(value)):
        raise ValueError(
            'Name must contain at least one letter that Swish can show')
    return value


Name = Annotated[str, AfterValidator(sanitize_name)]
NameList = Annotated[list[Name], Field(min_length=1, max_length=MAX_NAMES)]
# [0-9] rather than \d, which also matches non-ASCII digits.
SwishNumber = Annotated[str, StringConstraints(pattern=r'^[0-9]{10,15}$')]


class SwishQrData(BaseModel):
    """Validated input for app.payments.qr.generate_qr_png."""
    model_config = ConfigDict(frozen=True)

    names: NameList
    amount_ore: PositiveInt
    swish_number: SwishNumber


class PaymentRequestCreate(BaseModel):
    # Any other field (amount, message, ...) is a 422: the client's only input
    # is the names and the membership type.
    model_config = ConfigDict(extra='forbid')

    names: NameList
    membership_type_id: int


class PaymentRequestRead(BaseModel):
    id: UUID
    names: list[str]
    message: str
    amount_ore: int
    swish_number: str
    year: int
    created_at: datetime
    payment_url: str


class LinkedMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    member_number: str
    name: str


class LinkedFeeRead(BaseModel):
    """A fee paid through a payment request. A linked fee is always paid."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    paid_at: datetime
    member: LinkedMemberRead


class PaymentRequestAdminRead(PaymentRequestRead):
    fees: list[LinkedFeeRead]


class PaymentRequestList(BaseModel):
    # The year the backend chose, also when the list is empty.
    year: int
    items: list[PaymentRequestAdminRead]


def _unique(values: list[int]) -> list[int]:
    return list(dict.fromkeys(values))


class MarkFeesPaid(BaseModel):
    model_config = ConfigDict(extra='forbid')

    member_ids: Annotated[list[int], Field(min_length=1, max_length=20),
                          AfterValidator(_unique)]


class MarkFeesPaidResult(BaseModel):
    marked: int
    created: int
    already_paid: int
