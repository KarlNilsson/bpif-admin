from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends

TIME_ZONE = ZoneInfo('Europe/Stockholm')


def now() -> datetime:
    return datetime.now(TIME_ZONE)


def get_current_year() -> int:
    return now().year


CurrentYear = Annotated[int, Depends(get_current_year)]
