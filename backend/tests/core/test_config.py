from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

DATABASE_URL = 'postgresql+asyncpg://x:y@localhost/z'


def make_settings(**values: Any) -> Settings:
    return Settings(database_url=DATABASE_URL, **values)


def test_swish_number_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('SWISH_NUMBER', raising=False)

    with pytest.raises(ValidationError):
        make_settings()


@pytest.mark.parametrize('swish_number', [
    '123-456 78',
    '123456789',
    '1234567890123456',
])
def test_malformed_swish_number_is_rejected(swish_number: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(swish_number=swish_number)


def test_valid_swish_number_is_accepted() -> None:
    assert make_settings(swish_number='1231234567').swish_number == (
        '1231234567')
