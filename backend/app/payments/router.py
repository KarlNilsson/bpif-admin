from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from fastapi.concurrency import run_in_threadpool

from app.core.clock import CurrentYear
from app.core.config import SettingsDep
from app.core.database import DbSession
from app.payments import service
from app.payments.dependencies import ValidPaymentRequest
from app.payments.qr import generate_qr_png
from app.payments.schemas import (MarkFeesPaid, MarkFeesPaidResult,
                                  PaymentRequestCreate, PaymentRequestList,
                                  PaymentRequestRead, SwishQrData)

public_router = APIRouter(prefix='/payments', tags=['payments'])
admin_router = APIRouter(prefix='/payments', tags=['payments'])


@public_router.post('', status_code=status.HTTP_201_CREATED)
async def create_payment_request(data: PaymentRequestCreate,
                                 session: DbSession,
                                 settings: SettingsDep,
                                 year: CurrentYear) -> PaymentRequestRead:
    payment_request = await service.create_payment_request(
        session, data, settings.swish_number, year)
    return service.to_read(payment_request)


@public_router.get('/{payment_id}')
async def get_payment_request(
        payment_request: ValidPaymentRequest) -> PaymentRequestRead:
    return service.to_read(payment_request)


@public_router.get(
    '/{payment_id}/qr.png',
    response_class=Response,
    responses={200: {'content': {'image/png': {}},
                     'description': 'Swish QR code'}},
)
async def get_qr_code(payment_request: ValidPaymentRequest) -> Response:
    # Validates the stored row again before rendering. Sanitising is
    # idempotent, so valid stored names pass unchanged.
    data = SwishQrData(names=payment_request.names,
                       amount_ore=payment_request.amount_ore,
                       swish_number=payment_request.swish_number)
    png = await run_in_threadpool(generate_qr_png, data)
    # A payment request never changes. Private, because it contains names.
    return Response(png, media_type='image/png',
                    headers={'Cache-Control': 'private, max-age=86400'})


@admin_router.get('')
async def list_payment_requests(
        session: DbSession,
        current_year: CurrentYear,
        year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
        search: str | None = None,
        linked: bool | None = None) -> PaymentRequestList:
    return await service.list_payment_requests(
        session, year or current_year, search, linked)


@admin_router.post('/{payment_id}/mark-fees-paid')
async def mark_fees_paid(payment_id: UUID, data: MarkFeesPaid,
                         session: DbSession) -> MarkFeesPaidResult:
    return await service.mark_fees_paid(session, payment_id, data.member_ids)
