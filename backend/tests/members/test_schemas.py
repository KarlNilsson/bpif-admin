import pytest
from pydantic import ValidationError

from app.members.schemas import MemberCreate


def make(**overrides: object) -> MemberCreate:
    values = {'member_number': 'A-1', 'name': 'Anna Ek',
              'membership_type_id': 1}
    return MemberCreate.model_validate(values | overrides)


def test_member_number_is_trimmed() -> None:
    assert make(member_number=' A-1 ').member_number == 'A-1'


@pytest.mark.parametrize('member_number', ['A 1', 'Å1', 'A' * 21, ''])
def test_malformed_member_number_is_rejected(member_number: str) -> None:
    with pytest.raises(ValidationError):
        make(member_number=member_number)


def test_name_uses_the_payer_name_rules() -> None:
    assert make(name='  Anna   Ek 😀').name == 'Anna Ek'


def test_name_without_letters_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make(name='123')
