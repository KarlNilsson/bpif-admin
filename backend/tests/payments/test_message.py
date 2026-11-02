import random

import pytest
from pydantic import TypeAdapter, ValidationError

from app.payments.message import (MAX_MESSAGE_LENGTH, MESSAGE_PREFIX,
                                  SWISH_MESSAGE_CHARS, build_message,
                                  to_swish_text)
from app.payments.schemas import MAX_NAMES, NameList

name_list_adapter = TypeAdapter(NameList)


def test_single_name() -> None:
    assert build_message(['Anna Svensson']) == 'Medlemskap Anna Svensson'


def test_several_names_that_fit() -> None:
    names = ['Anna Svensson', 'Erik Berg', 'Åsa Ek']
    assert build_message(
        names) == 'Medlemskap Anna Svensson, Erik Berg, Åsa Ek'


def test_message_of_exactly_max_length_keeps_full_names() -> None:
    name = 'A' * (MAX_MESSAGE_LENGTH - len(MESSAGE_PREFIX))
    assert build_message([name]) == MESSAGE_PREFIX + name


def test_message_one_over_max_length_uses_initials() -> None:
    name = 'A' * (MAX_MESSAGE_LENGTH - len(MESSAGE_PREFIX) + 1)
    assert build_message([name]) == 'Medlemskap A'


def test_over_long_list_falls_back_to_initials() -> None:
    names = [
        'Anna Maria Svensson', 'Anna-Karin Berg-Ek', 'erik johansson',
        'Kalle',
    ]
    assert build_message(names) == 'Medlemskap AS, AB, EJ, K'


def test_initials_skip_words_without_letters() -> None:
    names = ['Anna Maria Svensson -', "- 'Erik Johansson Lindqvist"]
    assert build_message(names) == 'Medlemskap AS, EL'


def test_initials_keep_swedish_letters() -> None:
    names = ['Åsa Maria Öberg', 'Ärla Andersson Lindqvist']
    assert build_message(names) == 'Medlemskap ÅÖ, ÄL'


@pytest.mark.parametrize(('name', 'expected'), [
    ('José Müller', 'Jose Muller'),
    ('Søren Ærø', 'Soren Aero'),
    ("O'Brien", 'OBrien'),
    ('Åsa Öberg', 'Åsa Öberg'),
    ('Ängla Ågren', 'Ängla Ågren'),
    ('Åsa', 'Åsa'),
    ('Groß Łukasz Đorđe Þór', 'Gross Lukasz Dorde Thor'),
    ('Anna-Karin', 'Anna-Karin'),
    ('Ivan Петров', 'Ivan'),
    ('Ольга Ivan', 'Ivan'),
])
def test_to_swish_text_folds_names(name: str, expected: str) -> None:
    assert to_swish_text(name) == expected


def test_build_message_folds_names() -> None:
    assert build_message(['José Müller', "O'Brien"]) \
        == 'Medlemskap Jose Muller, OBrien'


def test_name_without_swish_letters_raises() -> None:
    with pytest.raises(ValueError):
        build_message(['Anna Svensson', 'Иван Петров'])


def test_worst_case_fits() -> None:
    words = 'Abcdefghij Klmnopqrst Uvwxyzåäöé Abcdefghij Klmnopqrst Uvwxyz'
    names = name_list_adapter.validate_python([words[:60]] * MAX_NAMES)
    assert all(len(name) == 60 for name in names)

    message = build_message(names)

    assert len(message) <= MAX_MESSAGE_LENGTH
    assert message == MESSAGE_PREFIX + ', '.join(['AU'] * MAX_NAMES)


RANDOM_NAME_CHARS = (
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    'åäöÅÄÖéèüøæßłđþñçÉÜØÆŁĐÞ'
    'ИванПетровОльга'
    "      -'’\t ​0123456789😀<>/;"
)


def random_name(rng: random.Random) -> str:
    length = rng.randint(1, 80)
    return ''.join(rng.choice(RANDOM_NAME_CHARS) for _ in range(length))


def test_random_valid_name_lists_give_valid_messages() -> None:
    rng = random.Random(20261030)
    checked = 0
    for _ in range(2000):
        count = rng.randint(1, MAX_NAMES)
        raw_names = [random_name(rng) for _ in range(count)]
        try:
            names = name_list_adapter.validate_python(raw_names)
        except ValidationError:
            continue

        message = build_message(names)

        assert len(message) <= MAX_MESSAGE_LENGTH, message
        assert set(message) <= SWISH_MESSAGE_CHARS, message
        assert message.startswith(MESSAGE_PREFIX)
        checked += 1

    assert checked > 200
