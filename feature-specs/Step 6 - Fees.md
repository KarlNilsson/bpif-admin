# Plan: Fees (step 6)

## Context

Step 6 of `Implementation.md` adds the yearly membership fee. Each member has at most one fee per year. An
administrator creates the year's fees, and marks a fee as paid once they have seen the payment in Swish. The
application never verifies payments itself: marking a fee as paid is always a manual action.

This step builds on step 5 (members, membership types, the `admin_router` in `main.py`, `ConfirmDialog`). Step 7
links payment requests to fees, and step 8 (later) shows a member their fee status.

Decisions made:

- **One fee per member, including families.** Each family member has their own fee with the "Familj" type and its
  amount (700 kr) as the snapshot. A single Swish payment covers all of them, and step 7 lets an admin mark them paid
  together. Summing fee amounts would count a family several times, so the overview shows **counts** (paid / unpaid /
  total), never totals in kronor.
- **Snapshots.** A fee stores the membership type and amount it was created with. Later changes to the member's type
  or the type's price never change an existing fee.
- **Idempotent generation.** "Create this year's fees" creates a fee for every active member who doesn't have one for
  that year, and nothing else. It's safe to re-run, e.g. after members join mid-year.
- **Explicit state transitions.** `mark-paid` only works on an unpaid fee, and `mark-unpaid` only on a paid one.
  Anything else gives 409. Each transition is a single atomic `UPDATE … WHERE status = …`, so two admins clicking at
  the same time can't both succeed.
- **"Current year" is the Stockholm calendar year**, decided by the backend (`CurrentYear` dependency), not by the
  browser's clock.
- **`marked_paid_by` is deferred to step 4.** There are no admin users yet. Step 4's migration adds a nullable
  `marked_paid_by_id` FK to the admin user. `mark_paid` sets it from `CurrentAdmin`, and `mark_unpaid` clears it.
- **Not public yet.** All fee endpoints are on the `admin_router`. **Don't deploy publicly before step 4.**

## Files

```
backend/
  pyproject.toml                       + tzdata
  alembic/versions/<rev>_fees.py
  app/
    main.py                            + fees admin_router
    models.py                          + fees
    core/clock.py                      TIME_ZONE, now(), get_current_year(), CurrentYear
    fees/
      __init__.py
      models.py                        FeeStatus, Fee
      schemas.py                       FeeRead, FeeSummary, FeeGenerate, FeeGenerationResult
      service.py
      router.py                        admin_router
      dependencies.py                  ValidFee
    members/service.py                 delete_member: ConflictError when the member has fees
    membership_types/service.py        delete_membership_type: also checks fees
  tests/
    conftest.py                        + get_current_year override helper
    factories.py                       + create_fee()
    core/test_clock.py
    fees/{__init__,test_service,test_router}.py
frontend/src/
  lib/
    api/fees.ts
    types/fees.ts
    utils/labels.ts                    + feeStatusLabels
    components/fees/FeeTable.svelte, FeeStatusBadge.svelte, FeeFilters.svelte
    components/layout/AdminNav.svelte  + "Avgifter"
  routes/(admin)/
    fees/+page.ts, +page.svelte
    members/[id=integer]/+page.ts, +page.svelte   + fee history
```

## 1. Current year (`app/core/clock.py`)

```python
TIME_ZONE = ZoneInfo('Europe/Stockholm')


def now() -> datetime:
    return datetime.now(TIME_ZONE)


def get_current_year() -> int:
    return now().year


CurrentYear = Annotated[int, Depends(get_current_year)]
```

- Add `tzdata` with `uv add tzdata`. The `python:3.13-slim` image isn't guaranteed to have a system time zone
  database, and `zoneinfo` falls back to the `tzdata` package.
- Tests pin the year with `app.dependency_overrides[get_current_year] = lambda: 2031`.

## 2. Model: `Fee` (`fees`)

| Column               | Type                                       | Notes                                         |
| -------------------- | ------------------------------------------ | --------------------------------------------- |
| `id`                 | `int` PK                                   |                                               |
| `member_id`          | FK → `members.id`, `RESTRICT`              |                                               |
| `year`               | `int`, indexed                             | CHECK `year BETWEEN 2000 AND 2100`            |
| `membership_type_id` | FK → `membership_types.id`, `RESTRICT`     | snapshot of the member's type                 |
| `amount_ore`         | `int`                                      | snapshot of the type's amount; CHECK `> 0`    |
| `status`             | `FeeStatus` (`unpaid`, `paid`)             | VARCHAR + CHECK, as in step 5; default unpaid |
| `paid_at`            | `DateTime(timezone=True)`, nullable        | set when marked paid                          |
| timestamps           | from `TimestampMixin`                      |                                               |

- Constraints:
  - `UniqueConstraint('member_id', 'year')` gives `uq_fees_member_id_year`, thanks to step 2's naming convention.
    It also serves as the index for `member_id`.
  - `CheckConstraint("(status = 'paid') = (paid_at IS NOT NULL)", name='paid_at_matches_status')` gives
    `ck_fees_paid_at_matches_status`. The database refuses a paid fee without a date, and an unpaid fee with one.
- Relationships: `member` and `membership_type`, both `lazy='raise'`.
- The migration is autogenerated and reviewed by hand: both CHECKs, the unique constraint, both `RESTRICT` FKs and
  `ix_fees_year`.

## 3. Schemas (`fees/schemas.py`)

- `FeeMemberRead`: `id`, `member_number`, `name`.
- `FeeMembershipTypeRead`: `id`, `name`. `MembershipTypeRead` is deliberately not reused, because its current
  `amount_ore` would sit confusingly next to the fee's snapshot.
- `FeeRead` (`from_attributes=True`):
  - `id`, `year`, `status`, `amount_ore`, `paid_at`
  - `member: FeeMemberRead`, `membership_type: FeeMembershipTypeRead`
  - `created_at`, `updated_at`
- `FeeSummary`: `year`, `total`, `paid`, `unpaid`.
- `FeeGenerate`: `year: int | None = Field(default=None, ge=2000, le=2100)`. `None` means the current year.
- `FeeGenerationResult`: `year`, `created`, `skipped`. `skipped` counts active members that already had a fee.

## 4. Service (`fees/service.py`)

- **`generate_fees(session, year) -> FeeGenerationResult`** is one statement:

  ```python
  insert(Fee)
  .from_select(
      ['member_id', 'year', 'membership_type_id', 'amount_ore', 'status'],
      select(Member.id, literal(year), Member.membership_type_id,
             MembershipType.amount_ore, literal(FeeStatus.UNPAID.value))
      .join(Member.membership_type)
      .where(Member.is_active),
  )
  .on_conflict_do_nothing(index_elements=['member_id', 'year'])
  .returning(Fee.id)
  ```

  - `created` is the number of returned ids. `skipped` is the active member count minus `created`.
  - `ON CONFLICT DO NOTHING` makes it idempotent and safe if run twice at the same time. Existing fees are never
    touched.
- **`get_fee(session, fee_id) -> Fee`** loads `member` and `membership_type`, with `populate_existing=True` so a fee
  changed by a Core `UPDATE` in the same session isn't stale. It raises `NotFoundError`.
- **`list_fees(session, year=None, status=None, search=None, member_id=None) -> Sequence[Fee]`**:
  - joins `Member` for the search (name `icontains`, member number `istartswith`, both with `autoescape=True`)
  - is ordered by member name, or by `year DESC` when `member_id` is given
  - loads `member` and `membership_type`
- **`get_fee_summary(session, year) -> FeeSummary`**: `count()` plus `count().filter(Fee.status == …)` in one query.
- **`mark_paid(session, fee_id) -> Fee`**:

  ```python
  update(Fee)
  .where(Fee.id == fee_id, Fee.status == FeeStatus.UNPAID)
  .values(status=FeeStatus.PAID, paid_at=func.now())
  .returning(Fee.id)
  ```

  - If no row is returned, `NotFoundError` if the fee doesn't exist, otherwise `ConflictError('Fee is already
    paid')`.
  - Commit and return `get_fee(...)`.
  - `mark_paid` stays unchanged in step 7. Step 7 adds bulk helpers (`create_missing_fees`, `mark_member_fees_paid`)
    that record the payment request instead.
- **`mark_unpaid(session, fee_id) -> Fee`** is the mirror image: `WHERE status = 'paid'`, it sets `unpaid` and
  `paid_at = NULL`, and raises `ConflictError('Fee is not paid')`.
- **`delete_fee(session, fee_id) -> None`** raises `ConflictError` for a paid fee. Mark it unpaid first, so a recorded
  payment is never removed by accident. It's meant for fees created by mistake, e.g. when a member's type was wrong;
  generating again recreates the fee.

**Guards in step 5's services**

- `delete_member` raises `ConflictError('Member has fees')` if any fee references the member. The UI then suggests
  deactivating instead.
- `delete_membership_type` raises `ConflictError` if a member **or a fee** references the type.

## 5. Router (`fees/router.py`)

`admin_router = APIRouter(prefix='/fees', tags=['fees'])`, included in the shared `admin_router` in `main.py`.

| Method and path                  | Query / body                                            | Response                    |
| -------------------------------- | ------------------------------------------------------- | --------------------------- |
| `GET /fees`                      | `year`, `status`, `search`, `member_id`                 | `list[FeeRead]`             |
| `GET /fees/summary`              | `year`                                                  | `FeeSummary`                |
| `POST /fees/generate`            | `FeeGenerate`                                           | `FeeGenerationResult`       |
| `POST /fees/{fee_id}/mark-paid`  |                                                         | `FeeRead`; 409 if paid      |
| `POST /fees/{fee_id}/mark-unpaid`|                                                         | `FeeRead`; 409 if unpaid    |
| `DELETE /fees/{fee_id}`          |                                                         | 204; 409 if paid            |

- `year` is `Annotated[int | None, Query(ge=2000, le=2100)]`.
  - `GET /fees` without `year` uses `CurrentYear`, except when `member_id` is given. Then it returns all years (the
    member's fee history).
  - `GET /fees/summary` and `POST /fees/generate` default to `CurrentYear`.
- The `summary` and `generate` paths are declared before the `{fee_id}` routes.

## 6. Frontend

All user-facing text is in Swedish. Regenerate the types and add `lib/types/fees.ts` (`Fee`, `FeeStatus`,
`FeeSummary`, `FeeGenerationResult`).

**`lib/api/fees.ts`:** `listFees(fetch, { year, status, search, memberId })`, `getFeeSummary(fetch, year?)`,
`generateFees(fetch, year?)`, `markFeePaid(fetch, id)`, `markFeeUnpaid(fetch, id)`, `deleteFee(fetch, id)`.

**`lib/utils/labels.ts`:** `feeStatusLabels = { unpaid: 'Obetald', paid: 'Betald' }`.

**`AdminNav`:** add "Avgifter" (`/fees`).

### `/fees` page

- `+page.ts`:
  - `depends('app:fees')`
  - reads `year`, `status` and `q` from the URL
  - runs `getFeeSummary(fetch, year)` and `listFees(fetch, { year, status, search: q })` in parallel. Without a year in
    the URL, both default to the backend's current year, and the page shows `summary.year`. The browser's clock is
    never used.
- `+page.svelte`:
  - The heading "Avgifter {år}" and the summary line "{paid} av {total} betalda · {unpaid} obetalda".
  - `FeeFilters`:
    - an "År" select, from the current year − 5 to + 1
    - a "Status" select: Alla, Obetalda, Betalda
    - a search field (debounced)
    - it updates the URL with `goto(..., { replaceState: true, keepFocus: true, noScroll: true })`, like the member
      list
  - The "Skapa avgifter för {år}" button opens a `ConfirmDialog` with the text:
    > Skapar en obetald avgift för varje aktiv medlem som saknar avgift för {år}, med medlemstypens nuvarande belopp.
    > Befintliga avgifter ändras inte.

    Confirming calls `generateFees`, shows the toast "{created} avgifter skapade, {skipped} fanns redan" and runs
    `invalidate('app:fees')`.
  - `FeeTable`.
  - The empty state, when no fees exist for the year, says "Inga avgifter för {år}" and points at the button.

### `FeeTable.svelte`

- Props: `{ fees: Fee[]; showMember?: boolean; onmarkpaid; onmarkunpaid; ondelete }`. The callbacks take the `Fee`
  and return `Promise<void>`.
- Columns:
  - Medlemsnr and Namn (a link to `/members/{id}`). Both are hidden when `showMember` is false.
  - År (only when `showMember` is false), Medlemstyp, Belopp (`formatCurrency`)
  - Status (`FeeStatusBadge`) and Betald (`formatDate(paid_at)`)
  - Actions
- Actions per row, each behind a `ConfirmDialog`:
  - Unpaid: **"Markera som betald"**. Title "Markera som betald?", text: "{namn} ({medlemsnr}), {medlemstyp},
    {belopp} för {år}. Kontrollera att betalningen syns i Swish innan du bekräftar."
  - Unpaid: "Ta bort" (destructive).
  - Paid: **"Ångra"**. Title "Ångra betalning?", text: "Avgiften markeras som obetald igen."

The page owns the handlers. After a success: a toast ("Avgiften är markerad som betald" / "Betalningen är ångrad" /
"Avgiften är borttagen"), then `invalidate('app:fees')`. A 409 shows the toast `errorMessage(e, { 409: 'Avgiften har
redan ändrats. Listan har uppdaterats.' })` and invalidates too, so the table shows the real state.

### Member detail page (`/members/[id=integer]`)

- The load also calls `listFees(fetch, { memberId: id })` (`depends('app:fees')`).
- A new "Avgifter" section renders `FeeTable` with `showMember={false}` and the same actions.
- Deleting a member with fees gives 409 and the toast from step 5: "… Inaktivera medlemmen i stället."

## 7. Tests

**`tests/factories.py`:** `create_fee(session, member=None, year=2030, status=FeeStatus.UNPAID, **overrides)`. A paid
fee gets `paid_at`.

**`tests/core/test_clock.py`**

- `now().tzinfo` is Europe/Stockholm, which proves `tzdata` is available in the image.
- `get_current_year()` equals `now().year`.

**`tests/fees/test_service.py`**

- Generate:
  - creates one unpaid fee per active member, with the member's type and the type's amount
  - skips inactive members
  - returns `created` / `skipped` correctly
  - running it again creates 0 and skips N
  - after the type's amount changes, existing fees keep the old amount and a re-run doesn't touch them
  - a member added later gets a fee from a re-run
  - two members with the "Familj" type each get their own 70000 fee
  - generating for another year creates separate fees
- `mark_paid` sets `status` and `paid_at`. A second call raises `ConflictError`, and an unknown id raises
  `NotFoundError`.
- `mark_unpaid` clears `paid_at`. Calling it on an unpaid fee raises `ConflictError`.
- `delete_fee` removes an unpaid fee and raises `ConflictError` for a paid one.
- `list_fees`:
  - filters by year, status and search (name, member-number prefix)
  - `member_id` returns all years, newest first
  - the default order is by member name
- `get_fee_summary` counts.
- Constraints:
  - inserting a paid fee without `paid_at` raises `IntegrityError` (the CHECK)
  - a second fee for the same member and year raises `IntegrityError`
- Step 5 guards:
  - deleting a member with a fee raises `ConflictError`
  - deleting a type referenced only by a fee (the member has since changed type) raises `ConflictError`

**`tests/fees/test_router.py`** (with `get_current_year` overridden to 2031)

- `GET /fees` without a year only returns 2031 fees, given fees in 2030 and 2031.
- `GET /fees?member_id=` returns both years.
- `GET /fees/summary` returns 2031 counts.
- `POST /fees/generate` with `{}` generates for 2031, and with `{"year": 2032}` for 2032.
- `mark-paid` gives 200, then 409. `mark-unpaid` gives 200, then 409. `DELETE` gives 204, and 409 for a paid fee.
  Unknown ids give 404.
- `?status=foo` and `?year=1999` give 422.

## Verification (definition of done)

1. `docker compose run --rm --entrypoint pytest backend` passes, including the migration-drift test.
2. In the UI, on `/fees`:
   1. "Skapa avgifter för {år}" creates fees for all active members.
   2. Running it again creates 0.
   3. Mark one as paid (confirm), filter by "Betalda", undo it, and delete an unpaid one.
   4. Two family members show up as two rows, and the summary counts both.
3. The member page shows the fee history. Deleting a member with fees shows the Swedish 409 toast.
4. Opening `/fees` in two tabs and marking the same fee as paid in both: the second tab shows the 409 toast and the
   refreshed state.
5. `npm run lint`, `npm run check` and `npm run build` pass. `npm run generate:types` gives no diff.

## Out of scope / follow-ups

- `marked_paid_by` and protecting the endpoints (step 4).
- Linking fees to payment requests and marking several fees paid in one action (step 7).
- A full audit history of paid/unpaid changes (an event log). Today only the latest state, `paid_at` and
  `updated_at` are kept.
- A payment date that differs from the time it was marked (e.g. taken from the bank statement). Fee totals in kronor
  (see the family decision). The public fee status (step 8).
