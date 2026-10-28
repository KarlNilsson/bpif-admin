import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def check_database(session: AsyncSession) -> bool:
    try:
        await session.execute(select(1))
    except (SQLAlchemyError, OSError):
        logger.warning('Database health check failed', exc_info=True)
        return False
    return True
