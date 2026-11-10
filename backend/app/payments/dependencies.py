from typing import Annotated
from uuid import UUID

from fastapi import Depends

from app.core.database import DbSession
from app.payments import service
from app.payments.models import PaymentRequest


async def valid_payment_request(payment_id: UUID,
                                session: DbSession) -> PaymentRequest:
    return await service.get_payment_request(session, payment_id)


ValidPaymentRequest = Annotated[PaymentRequest, Depends(valid_payment_request)]
