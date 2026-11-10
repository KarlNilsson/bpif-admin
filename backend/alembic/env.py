import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
import app.models  # noqa: F401  (registers every domain's models)
from app.core.config import get_settings
from app.core.database import Base

config = context.config

# A caller that passes in its own connection (the test harness) also owns the
# logging setup, so it isn't reconfigured from alembic.ini.
if (config.config_file_name is not None
        and 'connection' not in config.attributes):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    '''Run migrations in 'offline' mode, emitting SQL to the script output.'''
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    '''Create an engine from the settings (not alembic.ini, whose interpolation
    breaks on `%` in passwords) and run the migrations on a connection.'''
    connectable = create_async_engine(
        get_settings().database_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    '''Run migrations in 'online' mode.

    A caller may pass an open connection through
    `config.attributes['connection']` (the test harness does). Otherwise an
    engine is created from the settings.
    '''
    connection = config.attributes.get('connection')
    if connection is None:
        asyncio.run(run_async_migrations())
    else:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
