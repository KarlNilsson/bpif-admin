import pytest
from pydantic import TypeAdapter, ValidationError

from app.payments.schemas import MAX_NAMES, Name, NameList, SwishQrData

name_adapter = TypeAdapter(Name)
name_list_adapter = TypeAdapter(NameList)


def valid_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        'names': ['Anna Svensson'],
        'amount_ore': 30000,
        'swish_number': '1231234567',
    }
    return data | overrides


@pytest.mark.parametrize(('raw', 'expected'), [
    ('Anna\tSvensson', 'Anna Svensson'),
    ('Anna Svensson', 'Anna Svensson'),
    ('  Anna   Maria  Svensson ', 'Anna Maria Svensson'),
    ('Anna\nSvensson', 'Anna Svensson'),
])
def test_whitespace_is_collapsed_and_trimmed(raw: str, expected: str) -> None:
    assert name_adapter.validate_python(raw) == expected


def test_decomposed_characters_are_composed() -> None:
    result = name_adapter.validate_python('Åsa')
    assert result == 'Åsa'
    assert len(result) == 3


@pytest.mark.parametrize('raw', [
    'An​na',  # zero-width space
    'An‍na',  # zero-width joiner
    'An‮na',  # RTL override
    'An\x00na',
    'An\x07na',
    'An\x7fna',
])
def test_invisible_and_control_characters_are_removed(raw: str) -> None:
    assert name_adapter.validate_python(raw) == 'Anna'


@pytest.mark.parametrize(('raw', 'expected'), [
    ('Anna 😀 Svensson', 'Anna Svensson'),
    ('Anna2 Svensson', 'Anna Svensson'),
    ('<b>Anna</b>', 'bAnnab'),
    ('Anna; Svensson/', 'Anna Svensson'),
])
def test_emoji_digits_and_markup_are_removed(raw: str, expected: str) -> None:
    assert name_adapter.validate_python(raw) == expected


def test_typographic_apostrophes_become_ascii() -> None:
    assert name_adapter.validate_python('O’Brien') == "O'Brien"
    assert name_adapter.validate_python('O‘Brien') == "O'Brien"


def test_hyphens_and_non_swish_letters_are_kept() -> None:
    name = 'Anna-Karin Søren José'
    assert name_adapter.validate_python(name) == name


@pytest.mark.parametrize('names', [[], ['Anna'] * (MAX_NAMES + 1)])
def test_name_list_length_is_limited(names: list[str]) -> None:
    with pytest.raises(ValidationError):
        name_list_adapter.validate_python(names)


def test_name_list_accepts_max_names() -> None:
    names = name_list_adapter.validate_python(['Anna'] * MAX_NAMES)
    assert len(names) == MAX_NAMES


@pytest.mark.parametrize('raw', ['', '   ', '😀', '123', "-'-", '́'])
def test_name_without_letters_is_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        name_adapter.validate_python(raw)


def test_name_without_swish_letters_is_rejected() -> None:
    with pytest.raises(ValidationError):
        name_adapter.validate_python('Иван Петров')


def test_name_with_some_swish_letters_is_accepted() -> None:
    assert name_adapter.validate_python('Ivan Петров') == 'Ivan Петров'


def test_name_length_is_limited() -> None:
    assert name_adapter.validate_python('A' * 60) == 'A' * 60
    with pytest.raises(ValidationError):
        name_adapter.validate_python('A' * 61)


def test_name_length_is_checked_after_sanitizing() -> None:
    assert name_adapter.validate_python('A' * 60 + '😀' * 10) == 'A' * 60


def test_swish_qr_data_accepts_valid_input() -> None:
    data = SwishQrData.model_validate(valid_data(names=[' Anna  Svensson ']))
    assert data.names == ['Anna Svensson']
    assert data.amount_ore == 30000
    assert data.swish_number == '1231234567'


@pytest.mark.parametrize('amount_ore', [0, -100])
def test_amount_must_be_positive(amount_ore: int) -> None:
    with pytest.raises(ValidationError):
        SwishQrData.model_validate(valid_data(amount_ore=amount_ore))


def test_amount_of_one_ore_is_accepted() -> None:
    data = SwishQrData.model_validate(valid_data(amount_ore=1))
    assert data.amount_ore == 1


@pytest.mark.parametrize('swish_number', [
    '123123456',  # 9 digits
    '1' * 16,
    '123-1234567',
    '123 1234567',
    '+461231234567',
    '١٢٣١٢٣٤٥٦٧',  # Arabic-Indic digits
    '',
])
def test_invalid_swish_number_is_rejected(swish_number: str) -> None:
    with pytest.raises(ValidationError):
        SwishQrData.model_validate(valid_data(swish_number=swish_number))


@pytest.mark.parametrize('swish_number', ['1231234567', '1' * 15])
def test_valid_swish_number_is_accepted(swish_number: str) -> None:
    data = SwishQrData.model_validate(valid_data(swish_number=swish_number))
    assert data.swish_number == swish_number


def test_swish_qr_data_is_frozen() -> None:
    data = SwishQrData.model_validate(valid_data())
    with pytest.raises(ValidationError):
        data.amount_ore = 100
