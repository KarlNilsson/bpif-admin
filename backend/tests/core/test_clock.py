from zoneinfo import ZoneInfo

from app.core.clock import get_current_year, now


def test_now_is_in_stockholm_time() -> None:
    # Also proves that tzdata is available in the image.
    assert now().tzinfo == ZoneInfo('Europe/Stockholm')


def test_current_year_is_the_year_of_now() -> None:
    assert get_current_year() == now().year
