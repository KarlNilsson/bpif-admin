# Plan: Minimum models for step 7

## Context

Step 7 is specified in `Step 7 - Payment requests.md`, which assumes the full steps 5 and 6 are built first. None of
that exists yet: there are no `membership_types`, `members` or `fees` packages, no `core/clock.py`, and no Alembic
revisions. This plan cuts those steps down to what step 7 needs, so it can be built now and steps 5 and 6 only add to
it afterwards.

Step 7 has two parts, and they need different models:

| Part                                                     | Models needed                                        |
| -------------------------------------------------------- | ---------------------------------------------------- |
| **Phase 1, payer flow:** form → stored request → QR code | `MembershipType`, `PaymentRequest`                   |
| **Phase 2, admin matching:** request → members and fees  | Phase 1 + `Member`, `Fee`, `fees.payment_request_id` |

`Member` and `Fee` are only needed for matching (the "Yes" in `Implementation.md` to linking payment requests to member
and fee records). Each phase is shippable on its own and has its own migration. Phase 1 stores everything Phase 2
needs, so requests created in between can still be matched later.

Decisions made:

- **The model is `PaymentRequest`**.
- **A column is included now only if** step 7 reads or writes it, or it can't be correctly backfilled later. Everything
  else stays with step 5 or 6.
- **One link, no link table.** `fees.payment_request_id` is the only link. A fee has a member, so it links the request
  to both the member and the fee, and a family's payment is simply several fees pointing at one request. This replaces
  `payment_request_members` from the step 7 spec. See "Changes to the step 7 spec" for what that costs.
- **Strict subset of steps 5 and 6.** Table, column and constraint names are the ones in those specs.

## Phase 1: payer flow

### Models

**`MembershipType`** (`membership_types`)

| Column       | Type                 | Notes                                          |
| ------------ | -------------------- | ---------------------------------------------- |
| `id`         | `int` PK             |                                                |
| `name`       | `String(50)`, unique |                                                |
| `amount_ore` | `int`                | CHECK `amount_ore > 0` (`amount_ore_positive`) |

Seeded at the end of the migration with a lightweight `sa.table(...)`, never the ORM model, so the payer form works on
a fresh database:

| name       | amount_ore |
| ---------- | ---------- |
| Junior     | 30000      |
| Senior     | 50000      |
| Familj     | 70000      |
| Stödmedlem | 30000      |

**`PaymentRequest`** (`payment_requests`), as in the step 7 spec:

| Column         | Type                                              | Notes                                                        |
| -------------- | ------------------------------------------------- | ------------------------------------------------------------ |
| `id`           | `UUID` PK, `default=uuid4`                        | not guessable, because the QR endpoint is public             |
| `swish_number` | `String(15)`                                      | copied from the setting at creation                          |
| `name_list`    | `Text`                                            | sanitised names joined with `;`; `names` is a split property |
| `amount_ore`   | `int`, CHECK `amount_ore > 0`                     | the type's amount at creation                                |
| `year`         | `int`, indexed                                    | `CurrentYear` at creation                                    |
| `created_at`   | `DateTime(timezone=True)`, server default `now()` | `__mapper_args__ = {'eager_defaults': True}`                 |

There is deliberately no FK to `membership_types`: only the amount at the time matters.

### What the models need around them

- `core/clock.py` and `uv add tzdata`, taken from step 6 §1, for `year`.
- `Settings.swish_number: SwishNumber`, taken from step 7 §1. Add `SWISH_NUMBER` to `.env.example`, `docker-compose.yml`
  and both places in `ci.yml`. **An existing `.env` needs the new value too**, or compose refuses to start.
- `membership_types/`: `MembershipTypeRead`, `list_membership_types`, `get_membership_type` and the public
  `GET /membership-types`. No admin CRUD.
- `payments/`: `PaymentRequestCreate`, `PaymentRequestRead`, `create_payment_request`, `get_payment_request`, `to_read`,
  `ValidPaymentRequest`, and the public `POST /payments`, `GET /payments/{id}` and `GET /payments/{id}/qr.png`, as in
  step 7 §3-5.
- `app/models.py` imports both model modules, and `main.py` includes both public routers.
- Frontend: the payer form and QR page from step 7 §6. That spec moves the health card to `(admin)/status`, but
  `(admin)` doesn't exist in this phase, so it moves to `(public)/status` for now.

### Tests

- Seeded rows are exactly the four above.
- `test_config.py`, the amount table, "per request" and the `POST` / `GET` / `qr.png` router tests from step 7 §7.
  Leave out the tests for linking.
- `tests/factories.py` with `create_membership_type`.

### Done when

`docker compose run --rm --entrypoint pytest backend` passes, including the migration-drift test. The form produces a QR
code, and the manual Swish check in step 7's verification passes. This phase has no admin endpoints, so it doesn't wait
for step 4, but rate limiting is still missing until step 9.

## Phase 2: admin matching

### Models

**`Member`** (`members`)

| Column               | Type                                            | Notes                                                    |
| -------------------- | ----------------------------------------------- | -------------------------------------------------------- |
| `id`                 | `int` PK                                        |                                                          |
| `member_number`      | `String(20)`, unique                            | tells two people with the same name apart                |
| `name`               | `String(60)`, indexed                           | validated with `Name`, so it compares with payers' names |
| `membership_type_id` | FK → `membership_types.id`, `RESTRICT`, indexed | a new fee takes its type and amount from here            |

`membership_type` is a relationship with `lazy='raise'`.

**`Fee`** (`fees`)

| Column               | Type                                                      | Notes                                                    |
| -------------------- | --------------------------------------------------------- | -------------------------------------------------------- |
| `id`                 | `int` PK                                                  |                                                          |
| `member_id`          | FK → `members.id`, `RESTRICT`                             |                                                          |
| `year`               | `int`, indexed                                            |                                                          |
| `membership_type_id` | FK → `membership_types.id`, `RESTRICT`                    | snapshot; can't be backfilled once a member changes type |
| `amount_ore`         | `int`                                                     | snapshot; CHECK `> 0`                                    |
| `status`             | `FeeStatus` (`unpaid`, `paid`)                            | VARCHAR + CHECK, as in step 5                            |
| `paid_at`            | `DateTime(timezone=True)`, nullable                       |                                                          |
| `payment_request_id` | FK → `payment_requests.id`, `SET NULL`, indexed, nullable | set when paid through a request                          |

Constraints:

- `UniqueConstraint('member_id', 'year')`
- `paid_at_matches_status`: `(status = 'paid') = (paid_at IS NOT NULL)`
- `payment_request_requires_paid`: `payment_request_id IS NULL OR status = 'paid'`. This is new. Without a draft state,
  an unpaid fee must never hold a link, so the database refuses it.

Relationships, all `lazy='raise'`: `Fee.member` and `PaymentRequest.fees`.

### What the models need around them

All of these go on a shared `admin_router` in `main.py` (step 5 §5).

| Endpoint                              | Service                                                                                                  |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `GET /members?search=`                | `list_members`: search for the matching dialog                                                           |
| `POST /members`                       | `create_member`: otherwise nothing can be matched                                                        |
| `GET /payments?year=&search=&linked=` | `list_payment_requests`: `linked` uses `fees.any()`, loads `selectinload(fees).selectinload(Fee.member)` |
| `POST /payments/{id}/mark-fees-paid`  | `mark_fees_paid(session, id, member_ids)`, see below                                                     |
| `POST /fees/{id}/mark-unpaid`         | `mark_unpaid`: clears `paid_at` and `payment_request_id`; a mistaken match can be undone                 |

`mark_fees_paid` takes `{member_ids: list[int]}` (1–20 ids, `extra='forbid'`) and runs as one transaction:

1. Load the request and the members. A missing id raises `NotFoundError`.
2. `create_missing_fees(session, member_ids, pr.year)`: `INSERT … SELECT … ON CONFLICT DO NOTHING RETURNING id`, using
   each member's current type and amount.
3. `UPDATE fees SET status = 'paid', paid_at = now(), payment_request_id = :id WHERE member_id IN (…) AND year = :year
AND status = 'unpaid' RETURNING id`. Fees that are already paid keep their original request.
4. Commit once and return `MarkFeesPaidResult(marked, created, already_paid)`.

Frontend:

- A minimal `(admin)/+layout.svelte`, `AdminNav` and `ConfirmDialog` from step 5, and `FeeStatusBadge` from step 6.
- The `/payments` page from step 7 §6, with one change: the dialog's "Spara" becomes a confirmed "Markera avgifter som
  betalda", which sends the chosen members.
- Move the health card to `(admin)/status`.
- **There is no member UI in this phase.** Members are added through `/api/docs` until step 5's pages exist.

### Tests

- Constraints: each CHECK and the unique constraint raise `IntegrityError`. The drift test doesn't catch these, because
  Alembic doesn't compare CHECK constraints.
- `mark_fees_paid` with three members, where A has an unpaid fee, B a paid one and C none:
  - A becomes paid and linked.
  - B is unchanged, including its link.
  - C gets a new fee and it's marked paid.
  - The result is `marked=2, created=1, already_paid=1`. A second call gives `marked=0, created=0, already_paid=3`.
- A family: two members on one request gives two fees pointing at it, each with the snapshot 70000.
- A change to the type's amount doesn't change an existing fee.
- An unknown member raises `NotFoundError` and changes nothing.
- `mark_unpaid` clears the link, and the request is unlinked again if it was the last fee.
- `list_payment_requests` filters by year, search and `linked`.
- Creating a request links nothing, even when a member has exactly that name.
- Router status codes: 200, 404, 422.

### Done when

The tests pass, and in the UI a request can be matched to two members, one of them without a fee. Both show as paid, and
undoing one removes its link.

**Don't deploy this phase publicly before step 4.** `GET /members` would expose the register, and anyone could mark fees
as paid.

## Pitfalls

- **`get_settings` override.** `create_app()` calls `get_settings()` directly when `app.main` is imported, so overriding
  the dependency isn't enough: `SWISH_NUMBER` must be set in the test environment too.
- **Models must be registered together from Phase 2.** `fees.payment_request_id` refers to a table in another domain.
  Running only `pytest tests/fees` fails with an unresolved reference unless all models are imported. Add
  `from app import models  # noqa: F401` to `tests/conftest.py`. Don't use `import app.models` there, because the
  `app` fixture has the same name. The import doesn't need any environment variables, so pure unit tests still run
  without them.
- **Migration review.** Autogenerate must be checked by hand for the CHECKs, the three `ondelete` rules and the
  `Enum(native_enum=False, create_constraint=True)` rendering. Migration 2 must not change `payment_requests` itself.

## Left out, and who adds it

| Left out                                                      | Added by | Why it can wait                                                                                                        |
| ------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------- |
| `MembershipType.category`                                     | Step 5   | No rule reads it. The types are seeded, so a backfill by name is exact                                                 |
| Timestamps on types, members and fees                         | Step 5   | Nothing reads them. `paid_at` holds the date that matters                                                              |
| `Member.phone`                                                | Step 5   | Nullable, and step 7 never reads it                                                                                    |
| `Member.is_active`                                            | Step 5   | Server default `true`. Only `generate_fees` needs it                                                                   |
| Member and type CRUD, delete guards                           | Step 5   | Only the `POST` and search above are needed                                                                            |
| `generate_fees`, summary, fee list, `delete_fee`, `mark_paid` | Step 6   | Fees are created on demand when a request is matched                                                                   |
| `Fee.membership_type` relationship                            | Step 6   | The FK column is enough to write the snapshot                                                                          |
| `marked_paid_by_id`                                           | Step 4   | There are no admin users yet                                                                                           |
| Limits on names per membership type                           | Never    | Decided against in `QR module.md`. Line 435 of `Implementation.md` still says otherwise and needs updating (step 7 §8) |

Step 6 must reuse the `create_missing_fees` statement for `generate_fees`, and must keep `mark_unpaid` clearing the link.

## Changes to the step 7 spec

If this plan is accepted, update `Step 7 - Payment requests.md`:

- §2: remove `payment_request_members`, and add `payment_request_requires_paid`.
- §3: remove `PaymentRequestMembersUpdate`.
- §4: `set_members` and `mark_fees_paid` merge into the one action above.
- §5: remove `PUT /payments/{id}/members`.
- §6: `LinkMembersDialog` saves and marks in one step.
- §7: adjust the linking tests.

What the simpler model gives up:

- **No saved match before payment is confirmed.** An admin can't link members now and mark them paid later. The admin
  matches when they see the payment in Swish, so this should rarely matter.
- **A fee points at only one request.** If a payer generates two QR codes and pays one, only the paid one is linked,
  which is the correct result.

To keep the draft state instead, restore the link table and the separate `PUT`. All other parts of this plan stay the
same.

## Implementation notes

Both phases are built. Where the result differs from the plan above:

- **No `FeeStatusBadge`.** A linked fee is always paid, so the table uses a plain "Betald {datum}" badge and
  `LinkedFeeRead` has no `status`. Step 6 adds the component.
- **The health card went straight to `(admin)/status`,** since both phases were built together.
- **SvelteKit 3.** The installed version replaces two APIs the step 5–7 specs assume, so step 5 and 6 need the same
  changes:
  - Route matchers live in `src/params.ts` with `defineParams`, not in `src/params/<name>.ts`.
  - `goto` takes `{ replace: true, reset: false }`, not `{ replaceState: true, keepFocus: true, noScroll: true }`.
- **`app.payments.schemas` must not import models.** `app.core.config` imports `SwishNumber` from it, so importing
  anything that depends on the settings there creates an import cycle.
