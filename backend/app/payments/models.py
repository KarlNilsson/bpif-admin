from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.fees.models import Fee

# Sanitising only keeps letters, spaces, '-' and "'", so a name can never
# contain the separator.
NAME_SEPARATOR = ';'


class PaymentRequest(Base):
    """A generated Swish QR code. It does not mean anything has been paid."""
    __tablename__ = 'payment_requests'
    __table_args__ = (
        CheckConstraint('amount_ore > 0', name='amount_ore_positive'),
    )
    # Reads created_at back with RETURNING. An implicit load after the flush
    # would fail in an async session.
    __mapper_args__ = {'eager_defaults': True}

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Copied, so a QR code still pays the same recipient if the setting
    # changes.
    swish_number: Mapped[str] = mapped_column(String(15))
    name_list: Mapped[str] = mapped_column(Text)
    amount_ore: Mapped[int]
    year: Mapped[int] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())

    # The fees marked paid through this request.
    fees: Mapped[list['Fee']] = relationship(lazy='raise')

    @property
    def names(self) -> list[str]:
        return self.name_list.split(NAME_SEPARATOR)
