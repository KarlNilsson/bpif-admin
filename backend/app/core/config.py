from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from pydantic_settings import BaseSettings

from app.payments.schemas import SwishNumber


class Settings(BaseSettings):
    database_url: str
    swish_number: SwishNumber
    cors_origins: list[str] = []


@lru_cache
def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
