# Plan: Backend foundation (step 2)

## Context

Step 2 of `Implementation.md` gives the backend what every later domain step depends on:

- a test harness that runs against a dedicated PostgreSQL test database, with the schema created by the Alembic
  migrations and each test isolated in a rolled-back transaction
- domain exceptions that services raise and the app maps to HTTP status codes
- formatting and test tooling configured in `pyproject.toml`

The backend currently has `core/` (settings, engine, `get_db`), `health/` and the pure QR module in `payments/`. Its
tests in `tests/payments/` are pure unit tests. They don't need a database and must keep running without one. There is
no `conftest.py`. The pytest config has only `testpaths` and `pythonpath`. `alembic/env.py` has an empty model-import
section, and there are no revisions.

Decisions made:

- **Test database:** recreated on every pytest session (`DROP DATABASE … WITH (FORCE)` + `CREATE DATABASE`).
  `Implementation.md` only creates it when it's missing. Recreating it also works with an existing volume. It adds one
  guarantee: a migration edited during development, or a leftover from an aborted run, never leaks into the next run.
  The cost is about a second per run.
- **Test settings:** the test database URL is read in `tests/conftest.py`, not in `app.core.config.Settings`. The
  application never needs it.
- **Naming convention:** `uq` and `ix` names switch to `column_0_N_name` / `column_0_N_label`, so a multi-column
  constraint such as UNIQUE (`member_id`, `year`) gets a distinct, readable name (`uq_fees_member_id_year`). No
  revisions exist yet, so this costs nothing now and would need a migration later.
- **One model registry:** `app/models.py` imports every domain's `models` module. `alembic/env.py` and the
  migration-drift test both import it, so a new domain is registered in one place.
- **Error shape:** domain errors are returned as `{"detail": "<message>"}`, the same shape as FastAPI's
  `HTTPException`, so the frontend parses one shape. Messages are in English. The frontend owns all user-facing
  (Swedish) copy.

## Files

```
.env.example                          + TEST_DATABASE_URL
docker-compose.override.yml           backend: + TEST_DATABASE_URL
README.md                             + "Tests" section
backend/
  pyproject.toml                      [tool.autopep8]; extend [tool.pytest.ini_options]
  alembic/env.py                      accept a connection via config.attributes; import app.models
  app/
    models.py                         registry: imports every domain's models module (none yet)
    main.py                           register_exception_handlers(app)
    core/
      database.py                     naming convention update
      exceptions.py                   DomainError, NotFoundError, ConflictError, register_exception_handlers
  tests/
    conftest.py                       test DB lifecycle and the engine, db_session, app and client fixtures
    test_migrations.py                models match migrations; single head
    core/
      __init__.py
      test_exceptions.py
    health/
      __init__.py
      test_service.py
      test_router.py
```

## 1. Configuration

`.env.example` gets:

```
TEST_DATABASE_URL=postgresql+asyncpg://bpif:bpif-pw@db:5432/bpif_test
```

`docker-compose.override.yml` passes it to the backend, in development only. The production stack never sees it.

```yaml
backend:
  environment:
    TEST_DATABASE_URL: ${TEST_DATABASE_URL:?}
```

An existing `.env` must be updated, or `docker compose up` fails fast on the missing variable. The README notes this.

## 2. `app/core/database.py`: naming convention

```python
NAMING_CONVENTION = {
    'ix': 'ix_%(column_0_N_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_N_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}
```

The rest of the file is unchanged. Long lines are rewrapped by autopep8 (see 6).

## 3. `app/models.py` and `alembic/env.py`

`app/models.py` is the single place where models are registered:

```python
"""Imports every domain's models so that Base.metadata is complete.

Used by alembic/env.py (autogenerate) and tests/test_migrations.py.
"""
# import app.members.models  # noqa: F401  (added by each domain step)
```

`alembic/env.py`:

- The marked model-import section becomes `import app.models  # noqa: F401`.
- `run_migrations_online` uses a connection passed in through `config.attributes` when there is one. This is the
  standard Alembic recipe for sharing a connection, so the test harness can run migrations on its own engine:

  ```python
  def run_migrations_online() -> None:
      connection = config.attributes.get('connection')
      if connection is None:
          asyncio.run(run_async_migrations())
      else:
          do_run_migrations(connection)
  ```

`alembic upgrade head` from the entrypoint behaves exactly as before.

## 4. `app/core/exceptions.py`: domain errors

```python
class DomainError(Exception):
    """Base class for errors raised by services."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """The requested resource does not exist (404)."""


class ConflictError(DomainError):
    """The request conflicts with the current state (409)."""


STATUS_CODES: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
}


def register_exception_handlers(app: FastAPI) -> None:
    ...  # one handler per entry: JSONResponse({'detail': exc.message}, status_code)
```

- Services raise these exceptions and never `HTTPException`. Routers stay thin and don't translate errors.
- A bare `DomainError` isn't mapped. It's a programming error and surfaces as a 500.
- `create_app()` calls `register_exception_handlers(app)` before it includes the routers.

## 5. Test harness: `tests/conftest.py`

### Test database lifecycle

The session-scoped `engine` fixture does the following:

1. Read `TEST_DATABASE_URL` from the environment. Fail with a clear message if it's missing. Refuse to run if it
   equals `DATABASE_URL` or the database name doesn't end in `_test`. This guard is what makes "tests never touch the
   development database" hold.
2. Connect to the `postgres` maintenance database on the same server with `isolation_level='AUTOCOMMIT'`
   (`make_url(url).set(database='postgres')`). Run `DROP DATABASE IF EXISTS "<name>" WITH (FORCE)`, then
   `CREATE DATABASE "<name>"`. The compose and CI database users are superusers, so they may create databases.
3. Create the test engine with `create_async_engine(url, poolclass=NullPool)`. `NullPool` avoids connections leaking
   between event loops.
4. Run the migrations on it:

   ```python
   def _upgrade(connection: Connection) -> None:
       cfg = Config('alembic.ini')
       cfg.attributes['connection'] = connection
       command.upgrade(cfg, 'head')

   async with engine.begin() as connection:
       await connection.run_sync(_upgrade)
   ```

   `alembic.ini` is resolved relative to the backend root (`Path(__file__).parents[1]`), so pytest works from any
   working directory.
5. Yield the engine and dispose it afterwards. The database is left in place for inspection and dropped by the next
   run.

### Fixtures

| Fixture         | Scope    | What                                                                                                                                    |
| --------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `anyio_backend` | session  | Returns `'asyncio'`. Session scope lets the session-scoped async `engine` fixture share the event loop.                                 |
| `engine`        | session  | See above.                                                                                                                              |
| `db_session`    | function | Opens a connection, begins an outer transaction and yields `AsyncSession(bind=connection, join_transaction_mode='create_savepoint', expire_on_commit=False)`. Afterwards it closes the session and rolls back the outer transaction. |
| `app`           | function | Imports `create_app` inside the fixture and builds a fresh app per test. It sets `app.dependency_overrides[get_db]` to an async generator yielding `db_session`. |
| `client`        | function | `httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://test')`.                                                         |

- With `create_savepoint`, a service's `await session.commit()` only releases a savepoint, and the outer rollback
  still undoes everything. A service that catches `IntegrityError` and calls `await session.rollback()` rolls back to
  the savepoint, so the test can go on.
- `app.main` runs `create_app()` at import time, which needs `DATABASE_URL`. Importing it lazily inside the fixture
  keeps the pure unit tests (`tests/payments/`) runnable without any environment variables or database.
- `ASGITransport` doesn't run the lifespan, so `app.state.session_factory` is never created. Every DB access in tests
  goes through the `get_db` override.
- Later steps add overrides here, such as `get_settings` (step 7) and `get_current_year` (step 6).

### Conventions for test modules

- Async tests are marked with a module-level `pytestmark = pytest.mark.anyio`.
- `tests/` mirrors `app/`: `tests/<domain>/test_service.py` tests business rules directly with `db_session`, and
  `tests/<domain>/test_router.py` tests HTTP behaviour with `client`.

## 6. Tooling (`pyproject.toml`)

```toml
[tool.autopep8]
max_line_length = 79
recursive = true

[tool.pytest.ini_options]
testpaths = ['tests']
pythonpath = ['.']
addopts = ['--strict-markers', '-ra']
```

- The line length of 79 matches the payments code. Run `uv run autopep8 --in-place -r app tests alembic` once, to
  rewrap the few longer lines in `core/database.py` and the generated Alembic files.
- Check without changing anything: `uv run autopep8 --diff --exit-code -r app tests alembic`. The exit code is 2 when
  there is a diff, and CI uses this (step 3). From step 3 the command also includes `scripts`.

## 7. Tests

**`tests/health/test_service.py`**

- `check_database(db_session)` is `True`.
- `check_database` is `False` for a session bound to an engine that points at an unreachable port (e.g.
  `postgresql+asyncpg://x:y@127.0.0.1:1/none`). That covers the `OSError` branch without mocking.

**`tests/health/test_router.py`**

- `GET /api/v1/health` returns 200 with `{"status": "ok", "database": "ok"}`.
- With `get_db` overridden to yield the unreachable session, it returns 503 with `detail` `'Database unavailable'`.

**`tests/core/test_exceptions.py`**

- A small app built in the test with `register_exception_handlers` and two routes raising `NotFoundError('x')` and
  `ConflictError('y')` gives 404 `{"detail": "x"}` and 409 `{"detail": "y"}`.

**`tests/test_migrations.py`**

- `compare_metadata(MigrationContext.configure(sync_connection), Base.metadata)` is empty after `upgrade head`, with
  `app.models` imported. This catches a model change without a migration, or a migration edited out of sync with the
  models.
- `ScriptDirectory.from_config(cfg).get_heads()` has at most one head, so there are no diverging migration branches.

**Existing tests:** `tests/payments/` is unchanged and still passes without a database.

## 8. README

Add a "Tests" section:

- Run them with `docker compose run --rm --entrypoint pytest backend` (add `tests/health` or `-k …` to narrow it).
- They run against `bpif_test`, which is recreated on every run. The development database is never touched.
- The entrypoint is bypassed because the harness applies the migrations to the test database itself.
- After pulling this change, add `TEST_DATABASE_URL` to your `.env` (see `.env.example`).

## Verification (definition of done)

1. `docker compose run --rm --entrypoint pytest backend` passes: health, exceptions, migrations and payments.
2. Running it twice in a row passes both times, so recreating the database works with an existing volume.
3. Rows created in the dev database (`psql -h localhost -U bpif bpif`) are untouched after a test run.
4. `docker compose run --rm --entrypoint pytest backend tests/payments` passes, and so does `uv run pytest
   tests/payments` on the host without env vars. The pure tests don't need the database.
5. Removing `TEST_DATABASE_URL`, or pointing it at `bpif`, makes the DB tests fail with the guard message instead of
   running.
6. `docker compose run --rm --entrypoint autopep8 backend --diff --exit-code -r app tests alembic` gives no diff.
7. `docker compose up` still starts the stack, and the backend log shows Alembic running before uvicorn.

## Out of scope / follow-ups

- CI (step 3), domain models (steps 5–7) and auth overrides in fixtures (step 4).
- Downgrade round-trip tests. Each migration's `downgrade` is reviewed by hand instead.
