# Plan: Swish QR module (backend, step 7, QR part only)

## Context

Step 7 of `Implementation.md` covers Swish QR codes. This plan builds only its core: a pure Python module that takes
**a list of names, an amount and the club's Swish number** and returns a **PNG QR code** containing a Swish payment
link. Scanning it with the phone's regular camera opens the Swish app with the payee, amount and message prefilled. It
covers no database model, no endpoint, no `SWISH_NUMBER` setting and no membership types. Those come in later steps,
and the module is designed so they can call it unchanged:

- The future `POST /payments` service validates names with the same types.
- The service looks up the amount from the membership type (step 5).
- The `GET /payments/{id}/qr.png` router calls the module through `run_in_threadpool`.

Decisions made:

- The QR code holds a Swish payment link (`https://app.swish.nu/1/p/sw/?...`) rather than the app-only `C...;...;...;0`
  payload, so it can be scanned with the phone's regular camera.
- The caller passes the amount (in öre). The module knows nothing about membership types.
- The number of names is not tied to membership type. Any request takes 1 to `MAX_NAMES` names.
- Names are stored as entered (after validation and sanitising). Folding to Swish-safe characters happens only when
  the message is built.

The backend currently has only `core/` and `health/`, and no `tests/` folder or pytest config.

## Files

```
backend/
  pyproject.toml                 + qrcode, pillow; dev: zxing-cpp; [tool.pytest.ini_options]
  app/payments/
    __init__.py
    schemas.py                   Name / NameList types (validation + sanitising), SwishQrData input model
    message.py                   to_swish_text(), build_message(): the ≤50-character Swish message
    qr.py                        build_payload(), render_png(), generate_qr_png(): the public entry point
  tests/
    __init__.py
    payments/
      __init__.py
      test_schemas.py
      test_message.py
      test_qr.py
```

`message.py` is separate from `qr.py`: `qr.py` stays the "payload → PNG" module that `Implementation.md` describes,
and the message rules (the bulk of the business logic) can be tested on their own.

## 1. Dependencies (`pyproject.toml`)

- `uv add qrcode pillow`
- `uv add --dev zxing-cpp`: QR decoding with prebuilt wheels and no system libraries. It is used in one test that
  decodes the generated PNG back to its payload.
- Minimal pytest config. Step 2 extends it later.
  ```toml
  [tool.pytest.ini_options]
  testpaths = ['tests']
  pythonpath = ['.']
  ```
- Rebuild the dev image afterwards (`docker compose build backend`), since dependencies live in `/opt/venv` inside it.

## 2. `app/payments/schemas.py`: name validation and the input model

Constants: `MAX_NAMES = 10` and `MAX_NAME_LENGTH = 60`. `MAX_NAMES` is chosen so the message always fits in initials
form (see 3).

`sanitize_name(value: str) -> str` is used as an `AfterValidator` and applies these steps in order:

1. `unicodedata.normalize('NFC', value)`.
2. Map every whitespace character (tab, NBSP, etc.) to `' '`, and map `’` / `‘` to `'`.
3. **Keep only** letters (Unicode category `L*`, plus `M*` for combining marks), spaces, `-` and `'`. Everything else
   is silently dropped: control characters (`Cc`), format characters such as zero-width and RTL override (`Cf`), emoji
   and symbols, digits, `<>/;` and other markup characters.
4. Collapse runs of spaces and trim.
5. Reject with `ValueError` if the result has no letter, is longer than `MAX_NAME_LENGTH`, or `to_swish_text(result)`
   has no letter. The last check covers names made only of letters Swish can't show, such as Cyrillic, so the message
   always identifies the member.

Types:

- `Name = Annotated[str, AfterValidator(sanitize_name)]`
- `NameList = Annotated[list[Name], Field(min_length=1, max_length=MAX_NAMES)]`

`NameList` is reused later by the `PaymentRequestCreate` request schema.

The input model is `SwishQrData(BaseModel)` with `model_config = ConfigDict(frozen=True)`:

- `names: NameList`
- `amount_ore: PositiveInt`
- `swish_number: Annotated[str, StringConstraints(pattern=r'^\d{10,15}$')]` (digits only)

Building a `SwishQrData` is what guarantees the QR module never sees unvalidated input.

## 3. `app/payments/message.py`: the Swish message

Constants:

- `MAX_MESSAGE_LENGTH = 50`
- `MESSAGE_PREFIX = 'Medlemskap '`
- `SWISH_MESSAGE_CHARS`: a–z, A–Z, åäöÅÄÖ, 0–9, space and `:.,?!()-"`.

`to_swish_text(name: str) -> str` folds one sanitised name to characters Swish accepts:

1. Protect å/ä/ö/Å/Ä/Ö.
2. Apply an explicit map for letters that don't decompose: `ø→o`, `æ→ae`, `ß→ss`, `ł→l`, `đ→d`, `þ→th` (and their
   uppercase forms).
3. NFKD, then drop combining marks (`é→e`, `ü→u`).
4. Drop apostrophes and every character not in `SWISH_MESSAGE_CHARS`, then collapse spaces.

`build_message(names: Sequence[str]) -> str`:

1. `folded = [to_swish_text(n) for n in names]`.
2. `full = MESSAGE_PREFIX + ', '.join(folded)`. Return it if `len(full) <= 50`.
3. Otherwise use initials. For each name, split on spaces and take the first letter of the first word plus the first
   letter of the last word (just one letter for a one-word name), uppercased. Return
   `MESSAGE_PREFIX + ', '.join(initials)`. Examples: `Anna Maria Svensson` → `AS`, `Anna-Karin Berg-Ek` → `AB`.
4. Worst case: 11 + 10 × 2 + 9 × 2 = 49 characters, so it always fits. A final check still raises `ValueError` if
   the length is over 50 or any character is outside `SWISH_MESSAGE_CHARS`. It should never trigger, but it makes the
   hard Swish limit explicit.

## 4. `app/payments/qr.py`: payment link and PNG

Synchronous and pure. Callers use `run_in_threadpool` (noted in the module docstring).

Constants:

- `SWISH_PAYMENT_URL = 'https://app.swish.nu/1/p/sw/'`
- `EDITABLE_FIELDS = 'msg'`: the `edit` parameter, which lets the payer edit the message.
- `SOURCE = 'qr'`: the `src` parameter.

Functions:

- `format_amount(amount_ore: int) -> str`: whole kronor as `'300'`. Otherwise kronor with a decimal point, e.g.
  `'300.50'`.
- `build_payload(swish_number: str, amount_ore: int, message: str) -> str` returns the payment link
  `https://app.swish.nu/1/p/sw/?sw={swish_number}&amt={format_amount(amount_ore)}&msg={message}&edit=msg&src=qr`,
  with the parameters in that order. No currency parameter is sent.
  The query string is built with `urllib.parse.urlencode(..., quote_via=quote)`, so the message is percent-encoded as
  UTF-8: spaces become `%20` (not `+`) and `Å` becomes `%C3%85`.
- `render_png(payload: str) -> bytes`:
  1. Create `qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=4)`.
  2. Call `add_data` and `make(fit=True)`.
  3. Call `make_image()`, save it to a `BytesIO` as PNG and return the bytes.
- `generate_qr_png(data: SwishQrData) -> bytes` is the public entry point:
  `render_png(build_payload(data.swish_number, data.amount_ore, build_message(data.names)))`.

**Specification caveat.** The payment link format is not part of Swish's published API docs. Some details are
uncertain: whether Swish decodes `%20` and UTF-8 encoded å/ä/ö in the message correctly, whether `amt` expects a decimal
point or a decimal comma, and how the link behaves on a phone without Swish installed. All of it is isolated in
`build_payload` / `format_amount`, so a correction is a one-line change. It must
be confirmed by scanning a generated code with a phone camera (see Verification).

## 5. Tests (pure unit tests, no database or HTTP)

These tests need no `DATABASE_URL`, because nothing imports `app.main`.

**`test_schemas.py`**

- Whitespace (tab, NBSP, double spaces) is collapsed and trimmed.
- Decomposed `å` becomes `å` (NFC).
- Zero-width, RTL override and control characters are removed.
- Emoji and digits are removed. `<b>Anna</b>` loses its markup characters.
- `’` becomes `'`.
- Rejected input:
  - an empty list, and 11 names
  - an empty name, or one that is empty after filtering (`'😀'`, `'123'`)
  - a name made only of Cyrillic letters
  - a name longer than 60 characters
- `amount_ore` must be at least 1. `swish_number` rejects non-digits and wrong lengths.

**`test_message.py`**

- One name, and several names that fit, both give the exact expected string.
- An over-long list falls back to initials. A middle name is skipped, and hyphenated and one-word names are handled.
- Folding: `José Müller` → `Jose Muller`, `Søren Ærø` → `Soren Aero`, `O'Brien` → `OBrien`. `Åsa Öberg` is unchanged.
- Worst case: 10 names of 60 characters with multiple words gives a message of at most 50 characters.
- A seeded loop of randomly generated valid name lists always gives at most 50 characters, all in
  `SWISH_MESSAGE_CHARS`.

**`test_qr.py`**

- `build_payload` gives the exact string, e.g.
  `'https://app.swish.nu/1/p/sw/?sw=1231234567&amt=300&msg=Medlemskap%20Anna%20Svensson&edit=msg&src=qr'`.
- `format_amount(30000) == '300'` and `format_amount(30050) == '300.50'`.
- å/ä/ö are percent-encoded as UTF-8 (`Åsa` → `%C3%85sa`), and `parse_qs(urlsplit(url).query)` gives back exactly
  `sw`, `amt`, `msg`, `edit` and `src`, with `msg` equal to the original message.
- `render_png` output starts with the PNG signature, opens with Pillow (`Image.open(...).verify()`) and is in mode
  `1`/`L`.
- Round trip: `zxingcpp.read_barcodes(Image.open(png))[0].text == payload`, including a message with å/ä/ö.
- `generate_qr_png(SwishQrData(...))` works end to end.

## Verification

1. `cd backend && uv run pytest tests/payments`, or in Docker:
   `docker compose build backend && docker compose run --rm --entrypoint pytest backend tests/payments`.
2. `uv run autopep8 --diff -r app tests` gives no diff.
3. **Manual Swish check (required before step 7 is done):**
   1. Generate a PNG with a small script, e.g.
      `uv run python -c "from app.payments.qr import ...; open('qr.png','wb').write(...)"`, written to a temp folder.
   2. Use the club's real Swish number, an amount with öre (e.g. 300.50) and a message with spaces and å/ä/ö.
   3. Scan it with the phone's regular camera app (iOS and Android if possible) and confirm that it opens Swish with
      the payee, amount and message prefilled and the message editable.
   4. If the message shows `%20` or garbled å/ä/ö, or the amount is wrong, adjust `build_payload` / `format_amount`
      and the matching tests.

## Out of scope / follow-ups

- The `SWISH_NUMBER` setting, the `PaymentRequest` model and migration, the endpoints, and the `run_in_threadpool`
  call in the router (rest of step 7).
- Mapping membership type to amount (step 5).
- Updating `Implementation.md`:
  - Step 7 assumes membership type goes into the module and that names and type are coupled. Both decisions changed.  - Step 7's "test" that the amount comes from the membership type belongs with the service, not this module.
