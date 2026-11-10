# Plan: Swish payment requests (rest of step 7)

## Context

Step 7 of `Implementation.md` lets a payer generate a Swish QR code for a membership fee. Its core is already
merged (see `QR module.md`):

- `app/payments/schemas.py`: `Name`, `NameList` (validation and sanitising), `SwishNumber`, `SwishQrData`
- `app/payments/message.py`: `build_message()`, the Swish message of at most 50 characters
- `app/payments/qr.py`: `build_payload()` (Swish payment link), `render_png()`, `generate_qr_png()`

This step adds the rest:

- the club's Swish number as a setting
- stored payment requests
- the public endpoints: create a payment request, read it, and get its QR code as a PNG
- the payer's form and QR page in the frontend
- an admin view where payment requests are linked to members and their fees marked as paid

It builds on steps 2, 3, 5 and 6.

The rules from `CLAUDE.md` that this step must uphold:

- A QR code is only ever created by the API and returned as an image, never in the frontend.
- The client's only input is a list of names and a membership type. The amount comes from the membership type, and
  the message is built on the server.
- Names are validated and sanitised before they're stored.
- The Swish message never exceeds 50 characters.

Decisions made:

- **Linking is manual, and part of marking fees paid.** Creating a payment request links nothing. An administrator
  later chooses the members it concerns, with the submitted names pre-filled as search terms, and marks their fees paid
  in one action. Name matching is never automatic. There's no saved match before that action. See
  `Step 7 - Minimum models.md`.
- **Number of names is independent of the membership type** (as decided for the QR module). Any request takes 1–10
  names. The amount is **per request**, not per name.
- **Stored columns** are those listed in `Implementation.md`: `id`, `swish_number`, `name_list`, `amount_ore`, `year`
  and `created_at`. `amount` is named `amount_ore`, like the other money columns. The message and the payment link
  aren't stored: they're derived from the row with `build_message` / `build_payload`, which are deterministic. The
  membership type isn't stored; only its amount at the time matters.
- **UUID ids.** The QR image and the payer's page are reachable without authentication, so a payment request's id
  must not be guessable or enumerable. Anyone holding the id can see the names on it, and that's only the payer.
- **The Swish number is copied into each row**, so a QR code created earlier still pays the same recipient if the
  setting changes.
- **"Öppna Swish" link.** A payer on their phone can't scan a QR code on their own screen, so the API also returns
  the payment link the QR code holds (`payment_url`), and the page shows it as a button. The QR image itself is still
  generated only by the API.
- **The message stays editable.** As in the QR module, the payment link sends `edit=msg`: the payee and amount are
  locked, and the payer can change the message in Swish. The QR page asks the payer not to change it, because the
  admin uses it to match the payment.
- **Fee ↔ payment request.** When fees are marked paid through a payment request, each fee records it in a new
  nullable `fees.payment_request_id`. This is the only link: a fee has a member, so it links the request to both, and
  a family's payment is several fees pointing at one request. Undoing the payment clears it.
- **Admin endpoints are open until step 4.** The admin endpoints are on the shared `admin_router`. **Don't
  deploy publicly before step 4.**

## Files

```
.env.example                          + SWISH_NUMBER
docker-compose.yml                    backend: + SWISH_NUMBER
.github/workflows/ci.yml              + SWISH_NUMBER (backend job, types drift check)
Implementation.md                     updated with the decisions from steps 5–7 (see 8)
backend/
  alembic/versions/<rev>_payment_requests.py
  app/
    main.py                           + payments public_router / admin_router
    models.py                         + payments
    core/config.py                    + swish_number: SwishNumber
    payments/
      models.py                       PaymentRequest
      schemas.py                      + PaymentRequestCreate, PaymentRequestRead, PaymentRequestAdminRead, …
      service.py
      router.py                       public_router, admin_router
      dependencies.py                 ValidPaymentRequest
    fees/
      models.py                       + payment_request_id
      schemas.py                      FeeRead + payment_request_id
      service.py                      + create_missing_fees, mark_member_fees_paid; mark_unpaid clears the link
  tests/
    conftest.py                       + get_settings override (test Swish number)
    core/test_config.py
    payments/test_service.py, test_router.py      (new; the existing pure tests are unchanged)
frontend/src/
  params.ts                           defineParams: route matcher for [id=uuid]
  lib/
    api/client.ts                     export API_BASE
    api/payments.ts
    types/payments.ts
    utils/format.ts                   + formatSwishNumber
    components/payments/
      PaymentForm.svelte, MembershipTypePicker.svelte, NameListInput.svelte, PaymentQr.svelte
      PaymentRequestTable.svelte, LinkMembersDialog.svelte
    components/layout/AdminNav.svelte + "Betalningar", "Status"
  routes/
    (public)/+page.ts, +page.svelte                   payment form (replaces the health page)
    (public)/payments/[id=uuid]/+page.ts, +page.svelte  QR page
    (admin)/payments/+page.ts, +page.svelte           payment requests
    (admin)/status/+page.ts, +page.svelte             health card, moved from (public)/+page
```

## 1. Setting: the club's Swish number

- `Settings.swish_number: SwishNumber` reuses the type from `app.payments.schemas`: digits only, 10–15 characters.
  The field is required, so a missing or malformed `SWISH_NUMBER` stops the backend at startup, not at the first QR
  code.
- Add `SWISH_NUMBER=1231234567` to `.env.example` with a comment ("replace with the club's Swish number"), and pass
  `SWISH_NUMBER: ${SWISH_NUMBER:?}` to the backend in the base `docker-compose.yml`, since both environments need it.
- CI: set `SWISH_NUMBER=1231234567` in the backend job and in the step that exports the OpenAPI schema.

## 2. Models and migration

### `PaymentRequest` (`payment_requests`)

| Column         | Type                                      | Notes                                                            |
| -------------- | ----------------------------------------- | ---------------------------------------------------------------- |
| `id`           | `UUID` PK, `default=uuid4`                | not guessable                                                    |
| `swish_number` | `String(15)`                              | copied from the setting at creation                              |
| `name_list`    | `Text`                                    | sanitised names joined with `;`                                  |
| `amount_ore`   | `int`, CHECK `amount_ore > 0`             | the membership type's amount at creation                         |
| `year`         | `int`, indexed                            | `CurrentYear` at creation                                        |
| `created_at`   | `DateTime(timezone=True)`, server default `now()` | `__mapper_args__ = {'eager_defaults': True}`, see step 5 |

- `NAME_SEPARATOR = ';'`. Sanitising (`Name`) only keeps letters, spaces, `-` and `'`, so a name can never contain
  the separator, and splitting is lossless. The service still checks this before storing.
- `names` is a property: `self.name_list.split(NAME_SEPARATOR)`.
- `fees: Mapped[list[Fee]] = relationship(lazy='raise')`: the fees marked paid through this request.

### `fees.payment_request_id`

A nullable FK → `payment_requests.id` with `SET NULL`, indexed. It's set when a fee is marked paid through a payment
request, and cleared by `mark_unpaid`. `FeeRead` gains `payment_request_id: UUID | None`.

The CHECK `payment_request_requires_paid` (`payment_request_id IS NULL OR status = 'paid'`) makes the database refuse
an unpaid fee that holds a link.

The migration is autogenerated and reviewed by hand: the UUID column type, the CHECKs, the FK with its `ondelete` rule,
and the indexes. `app/models.py` imports `app.payments.models`.

## 3. Schemas (`app/payments/schemas.py`, additions)

```python
class PaymentRequestCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    names: NameList
    membership_type_id: int
```

`extra='forbid'` turns any other field (`amount`, `amount_ore`, `message`, `swish_number`, …) into a 422. The rule
that the client's only input is names and membership type is enforced by the schema, not by convention.

| Schema                       | Fields                                                                                                     |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `PaymentRequestRead`         | `id: UUID`, `names: list[str]`, `message`, `amount_ore`, `swish_number`, `year`, `created_at`, `payment_url` |
| `LinkedMemberRead`           | `id`, `member_number`, `name`                                                                                |
| `LinkedFeeRead`              | `id`, `paid_at`, `member: LinkedMemberRead`. A linked fee is always paid.                                    |
| `PaymentRequestAdminRead`    | `PaymentRequestRead` + `fees: list[LinkedFeeRead]`                                                         |
| `PaymentRequestList`         | `year`, `items: list[PaymentRequestAdminRead]`                                                             |
| `MarkFeesPaid`               | `member_ids: list[int]` (1–20, duplicates removed), `extra='forbid'`                                        |
| `MarkFeesPaidResult`         | `marked`, `created`, `already_paid`                                                                        |

`PaymentRequestList` carries `year`, so the admin page shows the year the backend chose, even when the list is empty.

## 4. Services

### `app/payments/service.py`

- **`create_payment_request(session, data, swish_number, year) -> PaymentRequest`**
  1. `membership_type = await get_membership_type(session, data.membership_type_id)`. An unknown id raises
     `NotFoundError` (404), and nothing is stored.
  2. `build_message(data.names)`, as a guard before storing anything. It can't fail for names that passed `NameList`,
     but it makes the 50-character rule an explicit precondition of storing.
  3. Check that no name contains `NAME_SEPARATOR` (`ValueError` otherwise, which would be a bug).
  4. Store `PaymentRequest(swish_number=swish_number, name_list=';'.join(data.names),
     amount_ore=membership_type.amount_ore, year=year)` and commit. **No members are linked.**
- **`get_payment_request(session, payment_id) -> PaymentRequest`** raises `NotFoundError`.
- **`to_read(payment_request) -> PaymentRequestRead`**:
  - `message = build_message(pr.names)`
  - `payment_url = build_payload(pr.swish_number, pr.amount_ore, message)`

  This is the same link that `generate_qr_png` encodes, and the tests assert that.
- **`list_payment_requests(session, year, search=None, linked=None) -> PaymentRequestList`**:
  - `search` uses `name_list.icontains(search, autoescape=True)`.
  - `linked=True` / `False` uses `PaymentRequest.fees.any()` / `~…any()`.
  - The list is newest first, with `selectinload(PaymentRequest.fees).selectinload(Fee.member)`, and each request's
    fees are ordered by member name.
- **`mark_fees_paid(session, payment_id, member_ids) -> MarkFeesPaidResult`**:
  1. Load the request and the members. If any id is missing, raise `NotFoundError` naming the missing ids.
  2. `created = await create_missing_fees(session, member_ids, pr.year)` creates the fees that don't exist yet, from
     each member's **current** membership type. This applies to inactive members too: the admin chose them
     explicitly.
  3. `marked = await mark_member_fees_paid(session, member_ids, pr.year, payment_request_id=pr.id)`.
  4. `already_paid = len(member_ids) - marked`.
  5. Commit **once**, so the whole action is atomic.

### `app/fees/service.py` (additions)

Both helpers join the caller's transaction and don't commit:

- `create_missing_fees(session, member_ids, year) -> int` uses the same `INSERT … SELECT … ON CONFLICT DO NOTHING
  RETURNING id` as `generate_fees`, restricted to the given members. `generate_fees` and this function share the
  statement builder.
- `mark_member_fees_paid(session, member_ids, year, payment_request_id) -> int` runs one `UPDATE fees SET status =
  'paid', paid_at = now(), payment_request_id = :id WHERE member_id IN (…) AND year = :year AND status = 'unpaid'
  RETURNING id`. Already-paid fees, and the payment request they were paid with, are left untouched.
- `mark_unpaid` also sets `payment_request_id = NULL`.

## 5. Routers

**`public_router = APIRouter(prefix='/payments', tags=['payments'])`**

| Method and path                      | Response                            | Notes                                                             |
| ------------------------------------ | ----------------------------------- | ----------------------------------------------------------------- |
| `POST /payments`                     | 201 `PaymentRequestRead`            | `PaymentRequestCreate`; `SettingsDep` and `CurrentYear` injected  |
| `GET /payments/{payment_id}`         | `PaymentRequestRead`                | for the payer's QR page (reload-safe)                             |
| `GET /payments/{payment_id}/qr.png`  | `image/png`                         | see below                                                         |

The QR endpoint:

```python
@public_router.get(
    '/{payment_id}/qr.png',
    response_class=Response,
    responses={200: {'content': {'image/png': {}}, 'description': 'Swish QR code'}},
)
async def get_qr_code(payment_request: ValidPaymentRequest) -> Response:
    data = SwishQrData(names=payment_request.names,
                       amount_ore=payment_request.amount_ore,
                       swish_number=payment_request.swish_number)
    png = await run_in_threadpool(generate_qr_png, data)
    return Response(png, media_type='image/png',
                    headers={'Cache-Control': 'private, max-age=86400'})
```

- Rendering is CPU-bound, so it runs in the thread pool and never blocks the event loop.
- Building `SwishQrData` validates the stored row again before rendering. Sanitising is idempotent, so valid stored
  names pass unchanged.
- A payment request never changes, so the image can be cached. It's `private` because it contains names.
- The image endpoint is the one place that uses `response_class` instead of a `response_model`. The `responses`
  entry documents it in OpenAPI.
- `payment_id: UUID`, so a malformed id gives 422 and an unknown one gives 404.

**`admin_router = APIRouter(prefix='/payments', tags=['payments'])`** (mounted on the shared `admin_router`)

| Method and path                               | Query / body                               | Response                  |
| --------------------------------------------- | ------------------------------------------ | ------------------------- |
| `GET /payments`                               | `year` (default `CurrentYear`), `search`, `linked` | `PaymentRequestList` |
| `POST /payments/{payment_id}/mark-fees-paid`  | `MarkFeesPaid`                             | `MarkFeesPaidResult`      |

## 6. Frontend

All user-facing text is in Swedish. Regenerate the types and add `lib/types/payments.ts`.

**`lib/api/payments.ts`**

- `createPaymentRequest(fetch, data)` and `getPaymentRequest(fetch, id)`.
- `qrImageUrl(id): string` returns `${API_BASE}/payments/${id}/qr.png`. It isn't a fetch: the browser loads the PNG
  as an `<img>` source. `API_BASE` is exported from `client.ts`, so the prefix stays in one place.
- `listPaymentRequests(fetch, { year, search, linked })` and `markPaymentFeesPaid(fetch, id, memberIds)`.

**`lib/utils/format.ts`:** `formatSwishNumber('1231234567')` gives `'123 123 45 67'`.

### Payer: `/` (payment form)

The page replaces the health page. `+page.ts` loads `listMembershipTypes(fetch)`.

- The heading is "Betala medlemsavgift", with the intro text "Välj medlemskap och fyll i namnen på dem som avgiften
  gäller. Du får en QR-kod att skanna med Swish."
- `PaymentForm.svelte` has props `{ membershipTypes; onsubmit: (data: PaymentRequestCreate) => Promise<void> }` and
  contains:
  - **`MembershipTypePicker`**: a shadcn `radio-group` of cards, each showing the type's name and
    `formatCurrency(amount_ore)`.
  - **`NameListInput`**: 1–10 rows, each an input with the placeholder "För- och efternamn" and a remove button when
    there's more than one row. "Lägg till namn" is disabled at 10. The hint reads "Ange alla som avgiften gäller, t.ex.
    hela familjen." `MAX_NAMES = 10` mirrors the backend's `MAX_NAMES`; the server is the one that enforces it.
  - The submit button "Skapa QR-kod", with a pending state.
- Before sending, blank rows are dropped. That's form housekeeping, not sanitising: all sanitising happens on the
  server. The form keeps a map from sent index to row, so errors land on the right row.
- On error:
  - A 422 with `fieldErrors(e)` key `names.{i}` shows "Namnet måste innehålla bokstäver och vara högst 60 tecken"
    under row *i*.
  - The key `names` shows "Ange mellan 1 och 10 namn".
  - A missing type shows "Välj ett medlemskap".
  - A 404 shows "Medlemskapet finns inte längre. Ladda om sidan."
- On success: `goto('/payments/{id}')`.

### Payer: `/payments/[id=uuid]` (QR page)

`src/params.ts` matches the UUID format, with `defineParams` from `@sveltejs/kit/params`. `+page.ts` loads
`orNotFound(getPaymentRequest(fetch, params.id), 'Betalningen hittades inte')`.

`PaymentQr.svelte` (props `{ payment: PaymentRequest }`) shows:

- `<img src={qrImageUrl(payment.id)} alt="QR-kod för Swish-betalning">`, at a fixed size so the layout doesn't jump
  while it loads
- Belopp (`formatCurrency`), Mottagare (`formatSwishNumber`), Meddelande (`payment.message`) and Namn (the sanitised
  names, so the payer sees exactly what was saved)
- an **"Öppna Swish"** button linking to `payment.payment_url`, with the instruction "På mobilen: tryck på knappen.
  På datorn: skanna QR-koden med mobilens kamera."
- "Ändra inte meddelandet i Swish – det används för att koppla betalningen till rätt medlem."
- "Avgiften markeras som betald när föreningen har stämt av betalningen."
- a link "Gör en ny betalning" (`/`)

### Admin: `/payments`

- `+page.ts`: `depends('app:payments')`, reads `year`, `q` and `linked` from the URL, and calls `listPaymentRequests`.
- `+page.svelte`:
  - The heading is "Betalningar {år}", using the response's `year`.
  - Filters: a year select, the search field "Sök på namn" and the checkbox "Visa bara ej kopplade".
  - `PaymentRequestTable` has these columns:
    - Skapad (`formatDateTime`)
    - Meddelande: the exact Swish message, which is what the admin sees in Swish
    - Belopp
    - Kopplade medlemmar: each name with a "Betald {datum}" badge and an "Ångra" action, or "Ingen"
    - Actions
- **"Markera avgifter som betalda"** opens `LinkMembersDialog`:
  - Props: `{ payment; onclose: () => void; onconfirm: (memberIds: number[]) => Promise<void> }`.
  - It has one search field per submitted name, pre-filled with that name. Members can be added to the selection and
    removed from it. Members already linked can't be added again.
  - Results come from `listMembers` (`lib/api`), called from the input handler with a 300 ms debounce, not from an
    `$effect`. Each result shows "{namn} ({medlemsnr}), {medlemstyp}" and a "Lägg till" button.
  - "Markera som betalda" opens a `ConfirmDialog` with the text:
    > Markerar avgifterna för {år} som betalda för: {namn}. Saknade avgifter skapas med medlemmens nuvarande medlemstyp.
    > Kontrollera att betalningen på {belopp} syns i Swish innan du bekräftar.

    Confirming calls `markPaymentFeesPaid`, shows the toast "{marked} avgifter markerade som betalda ({created} nya,
    {already_paid} var redan betalda)" and runs `invalidate('app:payments')`.
- **"Ångra"** opens a `ConfirmDialog`. Confirming calls `markFeeUnpaid`, which removes the link.

### Admin: `/status` and navigation

- The health card from step 3 moves to `(admin)/status`.
- `AdminNav` gains "Betalningar" and "Status".

Add the shadcn-svelte component this step needs: `npx shadcn-svelte@latest add radio-group`.

## 7. Tests

`conftest.py`'s `app` fixture overrides `get_settings` with a `Settings` that has `swish_number='1231234567'`. Router
tests override `get_current_year` with 2031.

**`tests/core/test_config.py`**

- `Settings` without `swish_number` raises `ValidationError`.
- `'123-456 78'`, 9 digits and 16 digits are rejected. `'1231234567'` is accepted.

**`tests/payments/test_service.py`**

- **The amount comes from the membership type**, using the seeded types from step 5:

  | Type       | Names                              | `amount_ore` |
  | ---------- | ---------------------------------- | ------------ |
  | Junior     | `['Anna Svensson']`                | 30000        |
  | Senior     | `['Erik Berg']`                    | 50000        |
  | Familj     | `['Anna Svensson', 'Erik Svensson']` | 70000      |
  | Stödmedlem | `['Lisa Ek']`                      | 30000        |

- The amount is per request: Junior with 3 names gives 30000.
- An unknown type raises `NotFoundError`, and no row is stored.
- `name_list` stores the sanitised names joined with `;`, e.g. `'Åsa Öberg;José Müller'`. Original letters are kept;
  folding only happens in the message. `names` round-trips. `swish_number` and `year` are the values passed in.
- Nothing is linked on create, even when a member with exactly the same name exists.
- `to_read`:
  - `message == build_message(names)`
  - `payment_url == build_payload(swish_number, amount_ore, message)`
- `mark_fees_paid`, with three members: A has an unpaid fee, B a paid one, C none.
  - A becomes paid, with `payment_request_id` set.
  - B is unchanged, including its `payment_request_id`.
  - C gets a new fee with C's current type and amount, and it's marked paid.
  - The result is `marked=2, created=1, already_paid=1`.
  - A second call gives `marked=0, created=0, already_paid=3`.
  - An unknown member raises `NotFoundError` and changes nothing.
- `mark_unpaid` on a fee paid through a request clears `payment_request_id`.
- `list_payment_requests` filters by year, search and `linked`, and returns newest first with each request's fees.

**`tests/payments/test_router.py`**

- `POST /payments` returns 201:
  - `id` is a UUID, `amount_ore` comes from the type, `swish_number` from the settings, and `year` is 2031
  - `message == 'Medlemskap Anna Svensson'`
  - `payment_url` starts with `https://app.swish.nu/1/p/sw/`
- Extra fields `amount`, `amount_ore`, `message` and `swish_number` (parametrised) each give 422.
- Validation edge cases, each giving 422:
  - `names: []` and 11 names
  - `['😀']`, `['123']`, `['Иван Петров']`
  - a 61-character name
  - a missing `membership_type_id`

  An unknown `membership_type_id` gives 404.
- Injection and invisible characters:
  - `['<script>alert(1)</script> Anna']` gives 201, and the stored name contains only letters, spaces, `-` and `'`.
  - Zero-width and RTL-override characters are removed.
- **Worst case:** 10 names of 60 characters, each with several words, give 201. `len(message) <= 50`, every
  character is in `SWISH_MESSAGE_CHARS`, and the decoded QR code's `msg` matches.
- `GET /payments/{id}` gives 200. An unknown UUID gives 404, and `abc` gives 422.
- `GET /payments/{id}/qr.png`:
  - 200, `content-type: image/png`, the PNG signature and a `Cache-Control` header
  - `zxingcpp` decodes it to exactly the response's `payment_url`
  - `parse_qs` gives `msg` of at most 50 characters
- Admin:
  - `GET /payments` returns `{year: 2031, items: [...]}`
  - `POST …/mark-fees-paid` gives 200, 404 for an unknown member, and 422 for an empty list

The existing pure tests (`test_schemas.py`, `test_message.py`, `test_qr.py`) are unchanged and must still pass.

## 8. Documentation

Update `Implementation.md` so it describes what was built:

- **Step 5:** the member data (member number entered by the admin, name, optional phone, type, active flag). Families
  are separate members with the Familj type. The seeded types.
- **Step 6:** one fee per member, including families, with counts rather than kronor totals. `marked_paid_by` moves
  to step 4.
- **Step 7:**
  - the number of names isn't tied to the type
  - payment requests are matched to members manually by an admin, and `fees.payment_request_id` is the only link
  - the column `amount_ore`
- **Step 4:** it protects the shared `admin_router` and the `(admin)` route group, and adds `marked_paid_by_id`.

The message editability is already recorded in `Implementation.md`: the payee and amount are locked, and the message
stays editable (`edit=msg`).

## Verification (definition of done)

1. `docker compose run --rm --entrypoint pytest backend` passes, including the migration-drift test and all payments
   tests.
2. On `http://localhost:5173/`:
   1. Choose "Familj" and enter two names, one with `å` and extra spaces. Submit.
   2. The QR page shows 700 kr, the message "Medlemskap …" and the cleaned-up names.
   3. Reloading the page still works.
   4. An emoji-only name shows the Swedish error under the right row.
3. `curl -i http://localhost:8000/api/v1/payments/<id>/qr.png` gives `image/png`. A random UUID gives 404.
4. On `/payments` (admin):
   1. "Markera avgifter som betalda" on a request, choosing two members, marks their fees and creates a missing one.
   2. The list shows them as paid, and undoing one clears its link.
5. `npm run lint`, `npm run check` and `npm run build` pass. `npm run generate:types` gives no diff, and CI is green.
6. **Manual Swish check (required before step 7 is done)**, carried over from `QR module.md`:
   1. Put the club's real Swish number in `.env`.
   2. Create a payment request, and temporarily use a type with öre (e.g. 300,50 kr) to check the amount format.
   3. Scan the QR code from a computer screen with the phone camera, on iOS and Android if possible. Also tap "Öppna
      Swish" on a phone.
   4. Confirm that Swish opens with the payee, amount and message prefilled, that the payee and amount are locked,
      and that the message can be edited.
   5. If the message shows `%20` or garbled å/ä/ö, or the amount is wrong, adjust `build_payload` / `format_amount`
      and their tests.

## Out of scope / follow-ups

- Protecting the admin endpoints and pages (step 4).
- Rate limiting. Until step 9 (`limit_req` in nginx), a script could create payment requests in bulk and use CPU on
  QR rendering.
- Retention and deletion of payment requests (they contain names) (step 9).
- Automatic name matching (decided against), verifying payments with Swish (never), and the public fee status
  (step 8).
