from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest
import zxingcpp
from PIL import Image

from app.payments.message import build_message
from app.payments.qr import (SWISH_PAYMENT_URL, build_payload, format_amount,
                             generate_qr_png, render_png)
from app.payments.schemas import SwishQrData

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
SWISH_NUMBER = '1231234567'


def decode_png(png: bytes) -> str:
    image = Image.open(BytesIO(png)).convert('L')
    results = zxingcpp.read_barcodes(image)
    assert len(results) == 1
    return results[0].text


def test_build_payload() -> None:
    payload = build_payload(SWISH_NUMBER, 30000, 'Medlemskap Anna Svensson')
    assert payload == (
        'https://app.swish.nu/1/p/sw/?sw=1231234567&amt=300'
        '&msg=Medlemskap%20Anna%20Svensson&edit=msg&src=qr'
    )


@pytest.mark.parametrize(('amount_ore', 'expected'), [
    (30000, '300'),
    (30050, '300.50'),
    (30005, '300.05'),
    (100, '1'),
    (1, '0.01'),
])
def test_format_amount(amount_ore: int, expected: str) -> None:
    assert format_amount(amount_ore) == expected


def test_build_payload_encodes_message_as_utf8() -> None:
    url = build_payload(SWISH_NUMBER, 30050, 'Medlemskap Åsa Öberg, Ärla Ek')

    assert '&msg=Medlemskap%20%C3%85sa%20%C3%96berg%2C%20%C3%84rla%20Ek&' \
        in url
    assert '+' not in url


def test_build_payload_round_trips_through_parse_qs() -> None:
    message = 'Medlemskap Åsa Öberg, Ärla Ek'
    parts = urlsplit(build_payload(SWISH_NUMBER, 30050, message))

    assert f'{parts.scheme}://{parts.netloc}{parts.path}' \
        == SWISH_PAYMENT_URL
    assert parse_qs(parts.query, strict_parsing=True) == {
        'sw': [SWISH_NUMBER],
        'amt': ['300.50'],
        'msg': [message],
        'edit': ['msg'],
        'src': ['qr'],
    }


def test_render_png_returns_valid_png() -> None:
    png = render_png('https://app.swish.nu/1/p/sw/?sw=1231234567')

    assert png.startswith(PNG_SIGNATURE)
    Image.open(BytesIO(png)).verify()
    with Image.open(BytesIO(png)) as image:
        assert image.format == 'PNG'
        assert image.mode in ('1', 'L')


@pytest.mark.parametrize('message', [
    'Medlemskap Anna Svensson',
    'Medlemskap Åsa Öberg, Ärla Ek',
])
def test_render_png_round_trip(message: str) -> None:
    payload = build_payload(SWISH_NUMBER, 30050, message)
    assert decode_png(render_png(payload)) == payload


def test_generate_qr_png_end_to_end() -> None:
    data = SwishQrData(names=['  Åsa  Öberg ', 'José Müller'],
                       amount_ore=30050, swish_number=SWISH_NUMBER)

    png = generate_qr_png(data)

    assert png.startswith(PNG_SIGNATURE)
    expected_message = 'Medlemskap Åsa Öberg, Jose Muller'
    assert build_message(data.names) == expected_message
    assert decode_png(png) \
        == build_payload(SWISH_NUMBER, 30050, expected_message)
