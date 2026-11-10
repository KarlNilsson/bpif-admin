# Plan: Members and membership types (step 5)

## Context

Step 5 of `Implementation.md` adds the club's register: the membership types (and their prices) and the members, with
admin CRUD in the API and in the frontend. Later steps depend on it:

- Fees (step 6) are created per member and snapshot the member's membership type and amount.
- Payment requests (step 7) take their amount from a membership type, and the payer's form lists the types. The
  public `GET /membership-types` endpoint is added here.

This step builds on step 2 (test harness, `NotFoundError` / `ConflictError`) and step 3 (shadcn-svelte, API client,
generated types, `(public)` route group).

Decisions made:

- **Minimal member data (GDPR):** member number, name, optional phone number, membership type and an active flag.
  Nothing else.
- **The member number is entered by the admin.** It's unique and separate from the internal database id, so numbers
  from an existing register can be carried over.
- **Families:** each family member is a separate member with the "Familj" type. There is no household table. Step 6
  gives each of them their own fee.
- **Member names use the payer-name rules.** `Member.name` is validated with `Name` from `app.payments.schemas`, the
  same trimming, NFC normalisation, character filtering and length limit as the names a payer enters. When an admin
  links a payment request to members in step 7, the names then compare like with like.
- **Deactivate, don't delete.** `is_active = false` keeps a member who has left, together with their fee history.
  Step 6 blocks deleting a member who has fees. Deletion for GDPR purposes comes in step 9.
- **Membership types are seeded by a data migration**, with the four types from `Implementation.md`, so the payer form
  works on a fresh database. Admins can edit them afterwards.
- **Prepared for authentication (step 4).** Every management endpoint is mounted on one `admin_router` in `main.py`.
  Step 4 protects all of them at once. Until then, these endpoints and pages are open to anyone who can reach the app.
  **Don't deploy publicly before step 4.**

## Files

```
backend/
  alembic/versions/<rev>_membership_types_and_members.py   schema + seed data
  app/
    main.py                     public/admin router assembly
    models.py                   + membership_types, members
    core/database.py            + TimestampMixin
    membership_types/
      __init__.py
      models.py                 MembershipCategory, MembershipType
      schemas.py                MembershipTypeCreate / Update / Read
      service.py
      router.py                 public_router, admin_router
      dependencies.py           ValidMembershipType
    members/
      __init__.py
      models.py                 Member
      schemas.py                MemberCreate / Update / Read, normalize_phone
      service.py
      router.py                 admin_router
      dependencies.py           ValidMember
  tests/
    factories.py                create_membership_type(), create_member()
    test_isolation.py
    membership_types/{__init__,test_service,test_router}.py
    members/{__init__,test_schemas,test_service,test_router}.py
frontend/src/
  params/integer.ts             route matcher for [id=integer]
  lib/
    api/membershipTypes.ts, api/members.ts
    types/membershipTypes.ts, types/members.ts
    utils/money.ts              kronorToOre, oreToKronor
    utils/labels.ts             Swedish labels for enum values
    components/
      common/ConfirmDialog.svelte
      layout/AdminNav.svelte
      members/MemberForm.svelte, MemberTable.svelte, MemberFilters.svelte
      membership-types/MembershipTypeForm.svelte, MembershipTypeTable.svelte
  routes/(admin)/
    +layout.svelte
    members/+page.ts, +page.svelte
    members/new/+page.ts, +page.svelte
    members/[id=integer]/+page.ts, +page.svelte
    membership-types/+page.ts, +page.svelte
```

## 1. Shared: `TimestampMixin` (`app/core/database.py`)

```python
class TimestampMixin:
    __mapper_args__ = {'eager_defaults': True}

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

`eager_defaults=True` makes INSERT and UPDATE fetch the server-generated values with `RETURNING`. Otherwise
SQLAlchemy expires `created_at` / `updated_at` after a flush, and reading them in the async session triggers an
implicit load, which raises `MissingGreenlet`.

## 2. Models

### `MembershipType` (`membership_types`)

| Column       | Type                                                 | Notes                                          |
| ------------ | ---------------------------------------------------- | ---------------------------------------------- |
| `id`         | `int` PK                                             |                                                |
| `name`       | `String(50)`, unique                                 | e.g. "Junior"                                  |
| `category`   | `MembershipCategory` (`active`, `passive`, `mixed`)  | VARCHAR + CHECK, see below                     |
| `amount_ore` | `int`                                                | CHECK `amount_ore > 0` (`amount_ore_positive`) |
| timestamps   | from `TimestampMixin`                                |                                                |

- `MembershipCategory(StrEnum)` is stored with `Enum(MembershipCategory, native_enum=False, create_constraint=True,
  length=20, name='membership_category', values_callable=lambda e: [m.value for m in e])`. That gives a VARCHAR and a
  CHECK constraint, not a PostgreSQL enum type, so adding a value later is a simple constraint change.
- The category describes the kind of membership (active = plays, passive = supporter, mixed = family). It's shown in
  the admin UI. No rule depends on it yet.
- Changing a type's amount only affects fees and payment requests created afterwards. Both store a snapshot (steps 6
  and 7).

### `Member` (`members`)

| Column               | Type                                    | Notes                                         |
| -------------------- | --------------------------------------- | --------------------------------------------- |
| `id`                 | `int` PK                                | internal id, used in URLs                     |
| `member_number`      | `String(20)`, unique                    | entered by the admin                          |
| `name`               | `String(60)`, indexed                   | sanitised with `Name`                         |
| `phone`              | `String(16)`, nullable                  | normalised, e.g. `0701234567`, `+46701234567` |
| `membership_type_id` | FK → `membership_types.id`, `RESTRICT`, indexed |                                       |
| `is_active`          | `bool`, default and server default true |                                               |
| timestamps           | from `TimestampMixin`                   |                                               |

- `membership_type: Mapped[MembershipType] = relationship(lazy='raise')`. Services load it explicitly with
  `selectinload(Member.membership_type)`.

### Migration

Generate it with `alembic revision --autogenerate -m 'membership types and members'` and review it by hand:

- The `membership_category` CHECK, `amount_ore_positive`, the unique constraints, the FK with `ondelete='RESTRICT'`
  and the indexes are all present, with convention names (`uq_members_member_number`,
  `fk_members_membership_type_id_membership_types`, …).
- Add the seed data at the end of `upgrade()`, using a lightweight `sa.table(...)` definition, never the ORM models:

  | name       | category | amount_ore |
  | ---------- | -------- | ---------- |
  | Junior     | active   | 30000      |
  | Senior     | active   | 50000      |
  | Familj     | mixed    | 70000      |
  | Stödmedlem | passive  | 30000      |

- `downgrade()` drops both tables.

`app/models.py` imports `app.membership_types.models` and `app.members.models`.

## 3. Schemas

**`membership_types/schemas.py`**

- `MembershipTypeCreate`:
  - `name`: stripped, 1–50 characters
  - `category: MembershipCategory`
  - `amount_ore: PositiveInt`
- `MembershipTypeUpdate`: the same fields, all optional.
- `MembershipTypeRead` (`from_attributes=True`): `id`, `name`, `category`, `amount_ore`.

**`members/schemas.py`**

- `MemberNumber = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r'^[A-Za-z0-9-]{1,20}$')]`.
- `normalize_phone(value: str | None) -> str | None`, used as a `BeforeValidator`:
  1. `None` or blank gives `None`.
  2. Remove spaces, `-`, `(` and `)`.
  3. The result must match `^\+?[0-9]{7,15}$`, otherwise raise `ValueError`.
- `MemberCreate`:
  - `member_number: MemberNumber`
  - `name: Name` (from `app.payments.schemas`)
  - `phone: Phone = None`
  - `membership_type_id: int`
  - `is_active: bool = True`
- `MemberUpdate`: the same fields, all optional, for PATCH.
- `MemberRead` (`from_attributes=True`):
  - `id`, `member_number`, `name`, `phone`, `is_active`
  - `membership_type: MembershipTypeRead`
  - `created_at`, `updated_at`

**Update semantics (both domains).** A field left out of the body is left unchanged: the service applies
`data.model_dump(exclude_unset=True)`. Sending an explicit `null` is only allowed for nullable columns (`phone`, which
it clears). For any other field it gives 422, enforced by a `model_validator(mode='after')` on the update schemas.

## 4. Services

All functions are `async`, take the `AsyncSession` as their first argument and raise domain exceptions.

**`membership_types/service.py`**

- `list_membership_types(session) -> Sequence[MembershipType]`, ordered by `amount_ore`, then `name`.
- `get_membership_type(session, type_id) -> MembershipType` raises `NotFoundError`.
- `create_membership_type(session, data) -> MembershipType` raises `ConflictError` on a duplicate name. It checks
  first, case-insensitively, and also catches `IntegrityError` for races; after one it calls `session.rollback()`
  before raising.
- `update_membership_type(session, type_id, data) -> MembershipType`, with the same conflict rule.
- `delete_membership_type(session, type_id) -> None` raises `ConflictError` if any member references the type. Step 6
  adds fees to this check. The FK `RESTRICT` is the safety net.

**`members/service.py`**

- `list_members(session, search: str | None = None, is_active: bool | None = None) -> Sequence[Member]`:
  - `search` matches `Member.name.icontains(search, autoescape=True)` or
    `Member.member_number.istartswith(search, autoescape=True)`. `autoescape` makes `%` and `_` in the input literal.
  - It's ordered by `name`, then `member_number`, with `selectinload(Member.membership_type)`.
  - There's no pagination: the register has a few hundred rows.
- `get_member(session, member_id) -> Member` loads `membership_type` and raises `NotFoundError`.
- `create_member(session, data) -> Member`:
  - The membership type must exist (`get_membership_type`, so `NotFoundError`).
  - A duplicate `member_number` raises `ConflictError`, with the same check-and-catch pattern as above.
  - It returns `await get_member(session, member.id)`, so the relationship is loaded for serialisation.
- `update_member(session, member_id, data) -> Member`, with the same rules for type and number.
- `delete_member(session, member_id) -> None`. Step 6 adds a `ConflictError` when the member has fees.

## 5. Routers and `main.py`

**`membership_types/router.py`** has two routers with the same prefix and tag
(`APIRouter(prefix='/membership-types', tags=['membership-types'])`):

| Router          | Method and path                    | Response                         |
| --------------- | ---------------------------------- | -------------------------------- |
| `public_router` | `GET /membership-types`            | `list[MembershipTypeRead]`       |
| `admin_router`  | `POST /membership-types`           | 201 `MembershipTypeRead`         |
| `admin_router`  | `PATCH /membership-types/{type_id}` | `MembershipTypeRead`            |
| `admin_router`  | `DELETE /membership-types/{type_id}` | 204                            |

**`members/router.py`** has only an `admin_router` (`prefix='/members'`, `tags=['members']`):

| Method and path                 | Query / body              | Response                   |
| ------------------------------- | ------------------------- | -------------------------- |
| `GET /members`                  | `search`, `active` (bool) | `list[MemberRead]`         |
| `POST /members`                 | `MemberCreate`            | 201 `MemberRead`           |
| `GET /members/{member_id}`      |                           | `MemberRead`               |
| `PATCH /members/{member_id}`    | `MemberUpdate`            | `MemberRead`               |
| `DELETE /members/{member_id}`   |                           | 204                        |

`dependencies.py` in each domain holds a fetch-or-404 helper, e.g.
`ValidMember = Annotated[Member, Depends(valid_member)]`, which calls `service.get_member`.

**`main.py`**

```python
api_router = APIRouter(prefix='/api/v1')
api_router.include_router(health_router)
api_router.include_router(membership_types_router.public_router)

# Every management endpoint is mounted here. Step 4 protects all of them with
# APIRouter(dependencies=[Depends(get_current_admin)]).
admin_router = APIRouter()
admin_router.include_router(membership_types_router.admin_router)
admin_router.include_router(members_router.admin_router)

api_router.include_router(admin_router)
app.include_router(api_router)
```

The URLs don't change (no `/admin` prefix). Whether a route is public is decided only by which router it's on.

## 6. Frontend

All user-facing text is in Swedish. Regenerate `lib/types/api.ts` (`npm run generate:types`) and add the aliases in
`lib/types/membershipTypes.ts` and `lib/types/members.ts`.

**API modules**

- `lib/api/membershipTypes.ts`: `listMembershipTypes(fetch)`, `createMembershipType(fetch, data)`,
  `updateMembershipType(fetch, id, data)`, `deleteMembershipType(fetch, id)`.
- `lib/api/members.ts`: `listMembers(fetch, { search, active })`, `getMember(fetch, id)`, `createMember(fetch, data)`,
  `updateMember(fetch, id, data)`, `deleteMember(fetch, id)`.

**Utilities**

- `lib/utils/money.ts`:
  - `kronorToOre(input: string): number | null` accepts `300`, `300,50` and `300.50`, and returns `null` when the
    input is invalid.
  - `oreToKronor(ore: number): string` gives `300` or `300,50`, for prefilling inputs.
- `lib/utils/labels.ts`: `categoryLabels = { active: 'Aktiv', passive: 'Passiv', mixed: 'Familj (blandad)' }`. Step 6
  adds the fee status labels.

**Shared components**

- `common/ConfirmDialog.svelte`: an `AlertDialog` wrapper with these props:
  - `open` (bindable), `title`, `description`, `confirmLabel`
  - `destructive?: boolean`
  - `onconfirm: () => Promise<void>`

  While `onconfirm` runs, the confirm button shows a pending state. Steps 6 and 7 reuse it.
- `layout/AdminNav.svelte`: navigation links with an active state from `page.url.pathname`.

**Admin layout: `routes/(admin)/+layout.svelte`**

- `SiteHeader` titled "BPIF – administration", with `AdminNav` in its snippet, and a wide container.
- Nav items: "Medlemmar" (`/members`) and "Medlemstyper" (`/membership-types`). Step 6 adds "Avgifter", and step 7
  adds "Betalningar" and "Status".
- Public pages don't link to the admin pages. Step 4 adds the login.

**`/members`**

- `+page.ts`:
  - `depends('app:members')`
  - reads `q` and `active` from `url.searchParams`; `active` defaults to `true`, and `all` shows everyone
  - calls `listMembers`
- `+page.svelte`:
  - `MemberFilters`: a search field debounced by 300 ms, and a select with "Aktiva", "Inaktiva" and "Alla". Changing
    a filter updates the URL with `goto(url, { replaceState: true, keepFocus: true, noScroll: true })`, so the load
    function re-runs and the filter survives a reload.
  - `MemberTable`: columns Medlemsnr, Namn (a link to the member), Telefon, Medlemstyp and Status (an
    "Aktiv"/"Inaktiv" badge). The empty state says "Inga medlemmar hittades".
  - A "Ny medlem" button.

**`/members/new`**

- Loads the membership types and renders `MemberForm`.
- `onsave` calls `createMember`, then shows the toast "Medlemmen har lagts till" and runs `goto('/members/{id}')`.

**`/members/[id=integer]`**

- `src/params/integer.ts` matches `^\d+$`, so `/members/abc` gives 404 without calling the API.
- `+page.ts` uses `depends('app:member')` and loads `orNotFound(getMember(fetch, id), 'Medlemmen hittades inte')` and
  the membership types.
- `+page.svelte`:
  - `MemberForm`, prefilled. `onsave` calls `updateMember`, then shows a toast and runs `invalidate('app:member')`.
  - "Inaktivera" / "Aktivera" (`PATCH is_active`).
  - "Ta bort" with a `ConfirmDialog`, followed by `goto('/members')`. A 409 (from step 6) shows the toast "Medlemmen
    har avgifter och kan inte tas bort. Inaktivera medlemmen i stället."
  - Step 6 adds a fee history section.

**`MemberForm.svelte`**

- Props: `{ member?: Member; membershipTypes: MembershipType[]; onsave: (data: MemberCreate) => Promise<void> }`.
- Fields: Medlemsnummer, Namn, Telefon (optional) and Medlemstyp (a select showing name and `formatCurrency`), plus
  Aktiv when editing.
- It holds its form state in `$state` and awaits `onsave`. On an `ApiError` it shows its own Swedish messages under
  the fields named by `fieldErrors(e)`:
  - member_number: "Endast bokstäver, siffror och bindestreck, högst 20 tecken"
  - name: "Ange ett namn med bokstäver, högst 60 tecken"
  - phone: "Ange ett giltigt telefonnummer"
  - a 409 gives "Medlemsnumret används redan" under Medlemsnummer
- The page that renders it does the API call, the toast and the navigation.

**`/membership-types`**

- The load function lists the types.
- `MembershipTypeTable` has columns Namn, Kategori, Belopp, and Redigera / Ta bort actions.
- "Ny medlemstyp" and "Redigera" open a `Dialog` with `MembershipTypeForm` (name, category select, amount in kronor
  converted with `kronorToOre`).
- A hint below the table: "Ändrade belopp gäller nya avgifter och betalningar. Befintliga avgifter behåller sitt
  belopp."
- Errors:
  - A duplicate name on create shows a field error, "Det finns redan en medlemstyp med det namnet".
  - A 409 on delete shows the toast "Medlemstypen används och kan inte tas bort".
- After each change: `invalidateAll()`.

Add the shadcn-svelte components this step needs: `npx shadcn-svelte@latest add checkbox`.

## 7. Tests

**`tests/factories.py`** has async helpers that `add` + `flush` and take keyword overrides. Their defaults are unique
per call (a counter), so tests don't collide:

- `create_membership_type(session, **overrides)`
- `create_member(session, **overrides)`, which creates a type when none is given

**`tests/test_isolation.py`** checks the step 2 harness with real tables. Two tests run in order:

1. The first creates a member through `members.service.create_member`, which commits.
2. The second asserts that the member doesn't exist.

**`membership_types/test_service.py`**

- The seeded rows are exactly Junior 30000/active, Senior 50000/active, Familj 70000/mixed and Stödmedlem
  30000/passive.
- The list is ordered by amount, then name.
- Create works. A duplicate name, including a case-only difference (`junior`), raises `ConflictError`.
- A partial update changes only the given fields. An unknown id raises `NotFoundError`.
- Deleting an unused type works. Deleting a type a member uses raises `ConflictError`.

**`membership_types/test_router.py`**

- `GET` returns 200 with the `MembershipTypeRead` shape.
- `POST` returns 201. An amount of 0, an empty name or an unknown category gives 422.
- `PATCH` returns 200 and `DELETE` returns 204.
- Deleting a referenced type gives 409. An unknown id gives 404.

**`members/test_schemas.py`**

- `member_number` is trimmed. Spaces, `å` and 21 characters are rejected.
- `name` is sanitised with the `Name` rules: `'  Anna   Svensson '` gives `'Anna Svensson'`, emoji are removed, and a
  name of only digits is rejected.
- `phone`:
  - `'070-123 45 67'` gives `'0701234567'`
  - `'+46 70 123 45 67'` gives `'+46701234567'`
  - `''` gives `None`
  - `'abc'` and `'123'` are rejected
- `MemberUpdate` rejects `{"name": null}` and accepts `{"phone": null}`.

**`members/test_service.py`**

- Create and get work, with the membership type loaded.
- An unknown type raises `NotFoundError`. A duplicate number raises `ConflictError`.
- Search:
  - finds a name substring case-insensitively, and a member number prefix
  - treats `%` and `_` literally
- The `is_active` filter works.
- A partial update works, and `phone: None` clears the phone.
- Changing the type works. Delete works.
- An unknown id raises `NotFoundError`.

**`members/test_router.py`**

- The CRUD status codes are 201, 200 and 204.
- The response has a nested `membership_type`.
- 404, 409 and 422 cases.
- `GET /members?search=…&active=false` filters the list.

## Verification (definition of done)

1. `docker compose run --rm --entrypoint pytest backend` passes, including the migration-drift test from step 2.
2. On the dev database, `docker compose exec backend alembic downgrade base` followed by
   `docker compose exec backend alembic upgrade head` works, and afterwards the four seeded types exist.
3. `/api/docs` shows the `membership-types` and `members` tags. `GET /api/v1/membership-types` lists the seeded
   types.
4. In the UI (`http://localhost:5173/members`):
   - create a member, find them by name and by member number, edit the phone, deactivate them and check that they
     disappear from the default list, then delete them
   - a duplicate member number shows the Swedish field error
   - `/members/999999` and `/members/abc` show the 404 page
5. On `/membership-types`: create, edit (amount `300,50`), and delete a type in use, which shows the toast.
6. `npm run lint`, `npm run check` and `npm run build` pass. `npm run generate:types` gives no diff.

## Out of scope / follow-ups

- Authentication for the admin endpoints and pages (step 4). **They are open until then.**
- Fees, and the delete guards that depend on them (step 6).
- Pagination, CSV import of an existing register, households, and per-season prices (fees and payment requests store
  snapshots instead).
- GDPR retention and deletion (step 9).
