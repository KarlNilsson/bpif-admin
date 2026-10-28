# Implementation plan

Phased plan for building bpif-admin as described in `CLAUDE.md`. Every step leaves the repository in a working state:
`docker compose up` starts the stack, tests pass and linting is clean. Step 1 is specified in detail. Later steps are
outlined and refined (including their open questions) when work on them starts.

## Overview

| Step | Name                    | Outcome                                                                          |
| ---- | ----------------------- | -------------------------------------------------------------------------------- |
| 1    | Infrastructure          | Skeleton apps, Dockerfiles and compose files; `docker compose up` works          |
| 2    | Backend foundation      | Test harness against a test database, domain error handling, tooling             |
| 3    | Frontend foundation     | shadcn-svelte, app shell, API client, generated types, formatting, CI            |
| 4    | Administrator auth      | Admin login; all management endpoints protected                                  |
| 5    | Members and memberships | Membership types and members with admin CRUD                                     |
| 6    | Fees                    | Yearly fees per member, marked as paid manually by an admin                      |
| 7    | Swish QR codes          | Validated name list + membership type → stored payment request → PNG QR code     |
| 8    | Member fee status       | Members can check whether this year's fee is paid, without exposing the register |
| 9    | Production readiness    | nginx hardening, rate limiting, backups, deployment docs                         |

## Decisions

- Python dependencies: **uv** with `pyproject.toml`, a `dev` dependency group and a committed `uv.lock`.
- Images: `python:3.13-slim`, `node:24-alpine` (LTS), `nginx:<stable>-alpine` and `postgres:18-alpine`, each pinned
  to a specific version.
- Dev and production share one Dockerfile per app with named stages (`dev`, `prod`). The compose files are additive:
  `docker-compose.yml` holds what both environments share, `docker-compose.override.yml` (applied automatically) adds
  development and selects `target: dev`, and `docker-compose.production.yml` (applied explicitly) adds production and
  selects `target: prod`. Development is the default.
- FastAPI serves its docs under the API prefix (`/api/docs`, `/api/v1/openapi.json`), so they are reachable through the
  Vite proxy and nginx, and so the frontend can generate types from them.
- A `GET /api/v1/health` endpoint that queries the database is the end-to-end smoke test for
  frontend → proxy → backend → database.

---

## Step 1 — Infrastructure

**Goal:** `docker compose up` starts `db`, `backend` and `frontend` in development mode, and
`docker compose -f docker-compose.yml -f docker-compose.production.yml up --build` starts the production stack. The
only feature is a health check that proves the whole chain works.

**Out of scope:** domain models, the test harness, shadcn-svelte, authentication and CI (steps 2–4).

### 1.1 Repository root

```
.gitattributes                 `* text=auto eol=lf` (at least `*.sh text eol=lf`): a CRLF entrypoint.sh breaks the container
.gitignore                     .env, editor/OS files (.vs/, .vscode/, .idea/, Thumbs.db, .DS_Store)
.env.example                   Template for .env (committed)
docker-compose.yml             Shared base stack
docker-compose.override.yml    Development additions (applied automatically)
docker-compose.production.yml  Production additions (applied explicitly with -f)
README.md                      Add a quick start: copy .env.example to .env, run docker compose up, list the URLs
```

`.env.example`:

```
POSTGRES_USER=bpif
POSTGRES_PASSWORD=bpif-pw
POSTGRES_DB=bpif
DATABASE_URL=postgresql+asyncpg://bpif:bpif-pw@db:5432/bpif
CORS_ORIGINS=[]
FRONTEND_PORT=8080
```

### 1.2 Backend skeleton

```
backend/
  pyproject.toml
  uv.lock
  .python-version          3.13 (the host may have a newer Python; uv installs 3.13 itself)
  .gitignore               .venv, __pycache__, .pytest_cache
  .dockerignore            .git, .env, .venv, __pycache__, .pytest_cache, *.pyc
  Dockerfile
  entrypoint.sh
  alembic.ini
  alembic/
    env.py
    script.py.mako
    versions/.gitkeep
  app/
    __init__.py
    main.py
    core/
      __init__.py
      config.py
      database.py
    health/
      __init__.py
      router.py
      schemas.py
      service.py
```

Domain packages only get the files they need. `health` has no models or dependencies.

- **`pyproject.toml`**: created with `uv init --app` and `uv add`. `requires-python = '>=3.13,<3.14'`.
  - Dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`.
  - `dev` group: `pytest`, `httpx`, `autopep8`.
  - `qrcode` and `pillow` are added in step 7.
- **`app/core/config.py`**: `Settings(BaseSettings)` with `database_url: str` (required, so a missing value fails
  fast) and `cors_origins: list[str] = []`. It reads environment variables only. `get_settings()` is wrapped in
  `@lru_cache`, and `SettingsDep = Annotated[Settings, Depends(get_settings)]`.
- **`app/core/database.py`**: contains the following.
  - `Base(DeclarativeBase)` with a `MetaData(naming_convention=...)`, so autogenerated constraint names are
    deterministic.
  - `create_engine(settings) -> AsyncEngine`.
  - `create_session_factory(engine) -> async_sessionmaker[AsyncSession]` with `expire_on_commit=False`.
  - `get_db(request)`, which yields a session from `request.app.state.session_factory`.
  - `DbSession = Annotated[AsyncSession, Depends(get_db)]`.

  The engine is created in the app lifespan, not at import time, so there are no module-level globals.

- **`app/main.py`**: `create_app() -> FastAPI` is the factory, and `app = create_app()` is what uvicorn loads. It does
  the following.
  - A `lifespan` creates the engine and session factory on `app.state` and disposes the engine on shutdown.
  - All routers are included under a parent `APIRouter(prefix='/api/v1')`, tagged per domain.
  - `docs_url='/api/docs'`, `openapi_url='/api/v1/openapi.json'` and `redoc_url=None`.
  - `CORSMiddleware` is added only when `cors_origins` is non-empty.
- **`app/health/`**: `service.check_database(session) -> bool` runs `select(1)` and returns `False` if the query
  fails. `GET /api/v1/health` returns `HealthRead(status='ok', database='ok')`, or raises `HTTPException(503)` when the
  database is unreachable.
- **Alembic**: run `uv run alembic init -t async alembic`, then change the following.
  - Remove `sqlalchemy.url` from `alembic.ini`.
  - In `env.py`, build the engine with `create_async_engine(get_settings().database_url, poolclass=NullPool)` rather
    than `config.set_main_option`, which breaks on `%` in passwords.
  - Set `target_metadata = Base.metadata`.
  - Add a marked section where every domain's `models` module is imported (empty for now).
  - With no revisions, `alembic upgrade head` is a no-op that succeeds.
- **`entrypoint.sh`**:

  ```sh
  #!/bin/sh
  set -e
  alembic upgrade head
  exec "$@"
  ```

- **`Dockerfile`** (backend):

  ```dockerfile
  FROM python:3.13-slim AS base
  COPY --from=ghcr.io/astral-sh/uv:<pinned> /uv /uvx /bin/
  ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
      PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
  RUN useradd --create-home --uid 1000 app
  WORKDIR /app
  COPY pyproject.toml uv.lock ./
  RUN uv sync --frozen --no-install-project --no-dev
  COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh
  ENTRYPOINT ["entrypoint.sh"]
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

  FROM base AS dev
  RUN uv sync --frozen --no-install-project   # adds the dev group (pytest, httpx, autopep8)
  COPY . .
  USER app

  FROM base AS prod
  COPY . .
  USER app
  ```

  - The virtualenv lives in `/opt/venv` and the entrypoint in `/usr/local/bin`, so the development bind mount of
    `./backend:/app` hides neither of them.
  - The dependency layer is built before the source is copied, so it is cached.

### 1.3 Frontend skeleton

Create the app with `npx sv create frontend`, using the minimal template, TypeScript, the ESLint add-on
(`eslint-plugin-svelte`) and npm. Commit `package-lock.json`.

```
frontend/
  Dockerfile
  nginx.conf
  .dockerignore            .git, .env, node_modules, .svelte-kit, build
  svelte.config.js         adapter-static with { fallback: 'index.html' }
  vite.config.ts
  src/
    lib/
      api/client.ts        Minimal shared wrapper: prefixes /api/v1, checks response.ok, parses JSON (expanded in step 3)
      api/health.ts        getHealth(fetch)
      types/health.ts      Health type mirroring HealthRead (generated from OpenAPI from step 3)
    routes/
      +layout.ts           export const ssr = false;
      +layout.svelte       Minimal shell rendering {@render children()}
      +error.svelte        Minimal error page (page from $app/state)
      +page.ts             load: getHealth(fetch)
      +page.svelte         Title and API/database status
```

- Replace `adapter-auto` with `@sveltejs/adapter-static`.
- **`vite.config.ts`**:
  - `server.proxy['/api']` targets `process.env.API_PROXY_TARGET ?? 'http://localhost:8000'`.
  - `server.watch.usePolling = process.env.WATCH_POLLING === 'true'`, because file events from a Windows bind mount do
    not reach the container.
- **`Dockerfile`** (frontend):

  ```dockerfile
  FROM node:24-alpine AS deps
  WORKDIR /app
  COPY package.json package-lock.json ./
  RUN npm ci

  FROM deps AS dev
  COPY . .
  CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

  FROM deps AS build
  COPY . .
  RUN npm run build

  FROM nginx:<stable>-alpine AS prod
  COPY nginx.conf /etc/nginx/conf.d/default.conf
  COPY --from=build /app/build /usr/share/nginx/html
  ```

- **`nginx.conf`**:

  ```nginx
  server {
      listen 80;
      root /usr/share/nginx/html;

      location /api/ {
          proxy_pass http://backend:8000;
          proxy_set_header Host $host;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
      }

      location / {
          try_files $uri $uri/ /index.html;
      }
  }
  ```

  `proxy_pass` has no trailing slash, so `/api/v1/...` is passed through unchanged.

### 1.4 Docker Compose

The compose files are additive. The base file holds what development and production share, and each environment file
only adds to it. Nothing is ever removed from the base (no `!reset` or `!override`), so leaving out a file can never
leak development settings such as bind mounts or a published database port into production.

| File                            | Applied                               | Adds                                                     |
| ------------------------------- | ------------------------------------- | -------------------------------------------------------- |
| `docker-compose.yml`            | Always                                | Services, builds, environment, healthcheck, volume       |
| `docker-compose.override.yml`   | Automatically, by `docker compose up` | Development: `dev` targets, bind mounts, reload, ports   |
| `docker-compose.production.yml` | Explicitly, with `-f` (see below)     | Production: `prod` targets, nginx port, restart policies |

**`docker-compose.yml`** (shared base). Each service gets only the variables it needs, through `environment` with
`${VAR:?}` interpolation from `.env`. No service publishes a port here.

- **`db`**:
  - `image: postgres:18-alpine`.
  - `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` come from `.env`.
  - Volume `db-data:/var/lib/postgresql`. From version 18 the image keeps its data in a version-specific
    subdirectory, so the volume is not mounted at `/data`.
  - Healthcheck `pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}` (interval 5s, retries 10).
- **`backend`**:
  - `build: ./backend`.
  - `DATABASE_URL` and `CORS_ORIGINS` (`${CORS_ORIGINS:-[]}`) come from `.env`.
  - `FORWARDED_ALLOW_IPS: '*'`. Uvicorn otherwise only trusts proxy headers from 127.0.0.1, and the backend is
    reachable only from inside the compose network.
  - `depends_on: db: condition: service_healthy`.
- **`frontend`**:
  - `build: ./frontend`.
  - `depends_on: [backend]`, because nginx must be able to resolve `backend` when it starts.
- Named volume `db-data`.

**`docker-compose.override.yml`** (development, applied automatically):

- **`db`**: `ports: ['5432:5432']`.
- **`backend`**:
  - `build.target: dev`.
  - `command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
  - `volumes: ['./backend:/app']`.
  - `WATCHFILES_FORCE_POLLING: 'true'`.
  - `ports: ['8000:8000']`.
- **`frontend`**:
  - `build.target: dev`.
  - `volumes: ['./frontend:/app', '/app/node_modules']`. The anonymous volume keeps the container's Linux
    `node_modules` instead of the host's.
  - `API_PROXY_TARGET: http://backend:8000` and `WATCH_POLLING: 'true'`.
  - `ports: ['5173:5173']`.

**`docker-compose.production.yml`** (production, applied explicitly):

- **`db`**: `restart: unless-stopped`.
- **`backend`**: `build.target: prod` (the default stage, stated explicitly) and `restart: unless-stopped`.
- **`frontend`**:
  - `build.target: prod`.
  - `ports: ['${FRONTEND_PORT:-8080}:80']`.
  - `restart: unless-stopped`.

Production runs with `docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build`. Naming the
files with `-f` is what keeps the development override out. On a Linux server,
`COMPOSE_FILE=docker-compose.yml:docker-compose.production.yml` in its `.env` makes a plain `docker compose up -d` do the
same.

### 1.5 Notes and pitfalls

- After changing `package.json`, run `docker compose up --build -V` so the anonymous `node_modules` volume is
  recreated.
- If `npm ci` in the container fails on a missing platform-specific optional dependency (for example
  `@rollup/rollup-linux-x64-musl`), regenerate `package-lock.json` without an existing `node_modules`.
- `alembic upgrade head` runs on every backend start, including with `--reload` in development, because it lives in
  the entrypoint.

### 1.6 Verification (definition of done)

1. Copy `.env.example` to `.env`, then run `docker compose up --build`. All three services start. The backend log shows
   Alembic's `Context impl PostgresqlImpl.` before uvicorn starts.
2. `curl http://localhost:8000/api/v1/health` returns `{"status":"ok","database":"ok"}`.
3. `http://localhost:8000/api/docs` shows the OpenAPI docs with a `health` tag.
4. `http://localhost:5173` shows the health status through the Vite proxy. Editing `+page.svelte` hot-reloads the page,
   and editing a backend file reloads uvicorn.
5. With `docker compose stop db`, the health endpoint returns 503.
6. `docker compose exec backend whoami` prints `app`.
7. Run `docker compose down`, then `docker compose -f docker-compose.yml -f docker-compose.production.yml up --build`.
   - `http://localhost:8080` shows the page through nginx.
   - A deep link such as `http://localhost:8080/members/1` serves the SPA.
   - `http://localhost:8080/api/v1/health` returns OK.
   - Ports 8000, 5173 and 5432 are not reachable from the host.
8. `docker compose down -v` followed by `docker compose up` works from an empty database volume.

---

## Step 2 — Backend foundation

- **Test database**: the `pytest` session fixture creates `bpif_test` if it is missing, so it works with an existing
  volume. It then runs `alembic upgrade head` against that database through the Alembic API, with `env.py` accepting a
  connection passed in through `config.attributes`. The database URL comes from a `TEST_DATABASE_URL` setting, set in
  the override. Tests never touch the development database.
- **Isolation**: each test runs in an outer transaction on its own connection, with
  `AsyncSession(bind=connection, join_transaction_mode='create_savepoint')`. The transaction is rolled back after the
  test.
- **Fixtures**:
  - `get_db` is overridden via `app.dependency_overrides`.
  - `anyio_backend` returns `'asyncio'`.
  - `client` is an `httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://test')`.
- **First tests**: `tests/health/` covers the service and the endpoint.
- **Errors**: `app/core/exceptions.py` defines a `DomainError` base with `NotFoundError` and `ConflictError`. Handlers
  registered in `create_app` map them to 404 and 409.
- **Tooling**: add `[tool.autopep8]` and `[tool.pytest.ini_options]` to `pyproject.toml`.
- **Run**: `docker compose run --rm --entrypoint pytest backend`.

## Step 3 — Frontend foundation

- Initialise shadcn-svelte (Tailwind) and add components with its CLI into `lib/components/ui`.
- Build the app shell in `+layout.svelte` (navigation, page frame) and a styled `+error.svelte`.
- Complete `lib/api/client.ts`:
  - Typed `get`, `post`, `put`, `patch` and `delete`.
  - An `ApiError` carrying the status and detail.
  - A helper that loads use to turn a 404 into `error(404, ...)`.
- Generate types with `openapi-typescript` from `/api/v1/openapi.json` into `lib/types/api.ts`, via an npm script
  `generate:types`. `lib/types` re-exports friendly aliases.
- Add `lib/utils/format.ts` with `formatCurrency(ore)` (`Intl.NumberFormat('sv-SE', { style: 'currency', currency: 'SEK' })`)
  and `formatDate`.
- Configure ESLint with `eslint-plugin-svelte` and `typescript-eslint`, enforce single quotes, and add `npm run lint`
  and `npm run check` (svelte-check).
- Add a GitHub Actions CI workflow that runs backend tests (with a Postgres service) and frontend lint, check and
  build.

## Step 4 — Administrator authentication

- Add an `auth` domain:
  - An `AdminUser` model with an argon2 password hash.
  - Login and logout endpoints.
  - A `CurrentAdmin = Annotated[AdminUser, Depends(get_current_admin)]` dependency on every management endpoint.
- Recommended: a server-side session in an HttpOnly, Secure, `SameSite=Strict` cookie. It is same-origin thanks to the
  proxy, so no tokens are stored in JavaScript.
- There is no self-registration. The first admin is created with a CLI command (e.g. `python -m app.auth.cli create-admin`).
- Frontend: a login page, an auth store in `lib/stores/auth.svelte.ts`, and a redirect to login on 401.
- **Open questions:** how many admins? Are roles needed? How are passwords reset?
  - _Only one admin role is required._
  - _Password resets shall be handled via email._

## Step 5 — Members and membership types

- `MembershipType`: name (active or passive) and amount in öre (an integer).
- `Member`: name, membership type and minimal contact details.
- Admin CRUD endpoints with `MemberCreate`, `MemberUpdate` and `MemberRead` schemas, plus the matching frontend
  pages: `/members` and `/members/[id]`.
- **Open questions:** which member data is actually needed (keep it minimal for GDPR)? Do amounts change per season, so
  that a per-year price is needed? Are members grouped into households or families?
  - _Only member data required to begin with is a membership id, the member's name and phone number (optional)._

## Step 6 — Fees

- `Fee`: member, year, membership type, an amount snapshot in öre, status (unpaid or paid), `paid_at` and `marked_paid_by`.
  Each member has at most one fee per year (unique on member and year).
- Admin actions:
  - Create this year's fees for all active members.
  - Mark a fee as paid, or undo that, with audit fields recorded.
  - List fees filtered by year and status.
- Frontend: a fee overview for the current year with filters and a confirmed "mark as paid" action.
- The application never verifies payments. Marking a fee as paid is always a manual admin action.

## Step 7 — Swish QR codes

- Add a `SWISH_NUMBER` setting for the club's Swish number.
- Add a `payments` domain:
  - `POST /api/v1/payments` takes only a list of names and a membership type id. It stores a payment request and
    returns its id and reference.
  - `GET /api/v1/payments/{id}/qr.png` returns `image/png`, usable directly as an `<img>` source.
- **Name validation and sanitisation** (Pydantic validators, applied before anything is stored):
  - The list has between 1 and N entries.
  - Each name is trimmed, NFC-normalised and has its whitespace collapsed.
  - Only letters, spaces, hyphens and apostrophes are allowed. Control characters, markup and emoji are silently filtered.
- The amount comes only from the membership type, and the message is built only on the server. The client has no
  other input.
- Each payment request is saved to the database. A payment request has the columns `id`, `swish_number`, `name_list` (all names as a semicolon-separated list), `amount`, `year` and `created_at`.
- The message is at most 50 characters and uses only characters Swish allows. This is checked against worst-case
  input.
- The QR service module `app/payments/qr.py` is a pure function from payload to PNG bytes using `qrcode` and `pillow`.
  Routers call it via `run_in_threadpool`.
- The payload follows Swish's prefilled QR code specification: payee, amount and message, with the fields locked from
  editing. Verify the current specification during implementation.
- The message used for generating the QR code is constructed like this:
  - 'Medlemskap {name1}(, {name2}...)'.
  - If the list of name exceeds 50 characters, convert it down to initials (first letter of first and last name respectively) for each name.
- Tests:
  - Validation edge cases (empty, too long, injection characters, emoji).
  - The 50-character limit.
  - The amount comes from the membership type.
    - Junior - 300kr (active)
    - Senior - 500kr (active)
    - Family (more than one name entered) - 700kr (mix of active and passive)
    - Supportive - 300kr (passive)
  - The response has the PNG content type and decodes.
- Frontend: a form (names and membership type) that shows the resulting QR image.
- **Open questions:**
  - Who generates QR codes: admins only, or payers publicly? This affects auth and rate limiting.
    - _The QR codes are dynamically generated by the backend based on the payer interaction with the form._
  - Is the amount per name or per request?
    - _Per request._
  - What is the message format, and what happens when it would exceed 50 characters? One option is a short reference
    code plus truncated names.
    - _Message format is a string, and due to a hard Swish limitation the message in the QR code can **never** exceed 50 characters_
    - _The message should contain the name of the member(s)._
  - Should a payment request link to member and fee records to make matching payments easier?
    - _Yes._

## Step 8 — Member fee status

- Add a public, unauthenticated way for a member to see whether this year's fee is paid. It must not allow listing or
  enumerating members.
- The response is minimal: paid or unpaid for the current year, and the date when it was paid.
- **Open question:** how does a member identify themselves? Options:
  - A personal, unguessable link or token per member (recommended).
  - The reference code from the Swish message.
  - Name plus a second identifier.
  - **Answer:** _Full name is enough. These records are public._

  Whichever is chosen needs rate limiting.

## Step 9 — Production readiness

- nginx:
  - Security headers (CSP, `X-Content-Type-Options`, `Referrer-Policy`) and gzip.
  - Long-lived caching for `/_app/immutable/` and `no-cache` for `index.html`.
  - `limit_req` on public endpoints.
- HTTPS termination (depends on the hosting, which is an open question).
- Scheduled `pg_dump` backups with a documented restore procedure.
- Structured logging, and GDPR retention and deletion for members and payment requests.
- Deployment documentation in `README.md`.
