"""Generates Swish payment QR codes as PNG images.

The functions here are synchronous and CPU-bound. Call them from async
code with `run_in_threadpool`.

The QR code holds a Swish payment link, so it can be scanned with the
phone's regular camera. The link format is not part of Swish's published
API docs; all of it is isolated in `build_payload` and `format_amount`.
"""

from io import BytesIO
from urllib.parse import quote, urlencode

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from qrcode.image.pil import PilImage

from app.payments.message import build_message
from app.payments.schemas import SwishQrData

SWISH_PAYMENT_URL = 'https://app.swish.nu/1/p/sw/'
EDITABLE_FIELDS = 'msg'
SOURCE = 'qr'


def format_amount(amount_ore: int) -> str:
    """Formats öre as kronor: 30000 -> '300' and 30050 -> '300.50'."""
    kronor, ore = divmod(amount_ore, 100)
    if ore == 0:
        return str(kronor)
    return f'{kronor}.{ore:02d}'


def build_payload(swish_number: str, amount_ore: int, message: str) -> str:
    query = urlencode(
        {
            'sw': swish_number,
            'amt': format_amount(amount_ore),
            'msg': message,
            'edit': EDITABLE_FIELDS,
            'src': SOURCE,
        },
        quote_via=quote,
    )
    return f'{SWISH_PAYMENT_URL}?{query}'


def render_png(payload: str) -> bytes:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10,
                       border=4, image_factory=PilImage)
    qr.add_data(payload)
    qr.make(fit=True)
    buffer = BytesIO()
    qr.make_image().save(buffer, format='PNG')
    return buffer.getvalue()


def generate_qr_png(data: SwishQrData) -> bytes:
    message = build_message(data.names)
    return render_png(
        build_payload(data.swish_number, data.amount_ore, message))
