import re
import unicodedata
from typing import Annotated

from pydantic import (AfterValidator, BaseModel, ConfigDict, Field,
                      PositiveInt, StringConstraints)

from app.payments.message import to_swish_text

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
