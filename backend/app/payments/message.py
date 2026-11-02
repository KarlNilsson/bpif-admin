"""Builds the Swish payment message, using characters Swish accepts."""

import re
import string
import unicodedata
from collections.abc import Sequence

MAX_MESSAGE_LENGTH = 50
MESSAGE_PREFIX = 'Medlemskap '
SWISH_MESSAGE_CHARS = frozenset(
    string.ascii_letters + 'åäöÅÄÖ' + string.digits + ' :.,?!()-"'
)

PROTECTED_CHARS = frozenset('åäöÅÄÖ')
# Letters that don't decompose under NFKD, so they need an explicit mapping.
LETTER_MAP = {
    'ø': 'o', 'Ø': 'O',
    'æ': 'ae', 'Æ': 'Ae',
    'ß': 'ss', 'ẞ': 'Ss',
    'ł': 'l', 'Ł': 'L',
    'đ': 'd', 'Đ': 'D',
    'ð': 'd', 'Ð': 'D',
    'þ': 'th', 'Þ': 'Th',
}


def _fold_char(char: str) -> str:
    if char in PROTECTED_CHARS:
        return char
    if char in LETTER_MAP:
        return LETTER_MAP[char]
    decomposed = unicodedata.normalize('NFKD', char)
    return ''.join(c for c in decomposed if not unicodedata.combining(c))


def to_swish_text(name: str) -> str:
    """Folds a name to Swish characters: 'José Müller' -> 'Jose Muller'."""
    normalized = unicodedata.normalize('NFC', name)
    folded = ''.join(_fold_char(c) for c in normalized)
    # Apostrophes are not in SWISH_MESSAGE_CHARS, so they are dropped too.
    kept = ''.join(c for c in folded if c in SWISH_MESSAGE_CHARS)
    return re.sub(' +', ' ', kept).strip()


def _initials(folded_name: str) -> str:
    words = [w for w in folded_name.split(' ')
             if any(c.isalpha() for c in w)]
    first_letters = [next(c for c in w if c.isalpha()).upper()
                     for w in words]
    if len(first_letters) == 1:
        return first_letters[0]
    return first_letters[0] + first_letters[-1]


def build_message(names: Sequence[str]) -> str:
    """Builds the Swish message for the given names.

    Uses the full names if they fit within MAX_MESSAGE_LENGTH, otherwise
    the initials of each name's first and last word.
    """
    folded = [to_swish_text(name) for name in names]
    for name, folded_name in zip(names, folded):
        if not any(c.isalpha() for c in folded_name):
            raise ValueError(
                f'Name has no letters that Swish can show: {name!r}')

    message = MESSAGE_PREFIX + ', '.join(folded)
    if len(message) > MAX_MESSAGE_LENGTH:
        initials = [_initials(name) for name in folded]
        message = MESSAGE_PREFIX + ', '.join(initials)

    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(
            f'Swish message exceeds {MAX_MESSAGE_LENGTH} characters: '
            f'{message!r}')
    if not set(message) <= SWISH_MESSAGE_CHARS:
        raise ValueError(
            f'Swish message contains invalid characters: {message!r}')
    return message
