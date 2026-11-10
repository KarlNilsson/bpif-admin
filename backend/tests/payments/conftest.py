import pytest
from fastapi import FastAPI

TEST_YEAR = 2031


@pytest.fixture
def current_year(app: FastAPI) -> int:
    """Pins the backend's current year for router tests."""
    from app.core.clock import get_current_year

    app.dependency_overrides[get_current_year] = lambda: TEST_YEAR
    return TEST_YEAR
