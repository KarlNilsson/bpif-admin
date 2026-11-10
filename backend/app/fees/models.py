from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (CheckConstraint, DateTime, Enum, ForeignKey,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.members.models import Member


class FeeStatus(StrEnum):
    UNPAID = 'unpaid'
    PAID = 'paid'


class Fee(Base):
    __tablename__ = 'fees'
    __table_args__ = (
        UniqueConstraint('member_id', 'year'),
        CheckConstraint('amount_ore > 0', name='amount_ore_positive'),
        CheckConstraint("(status = 'paid') = (paid_at IS NOT NULL)",
                        name='paid_at_matches_status'),
        # Matching a request marks the fee paid in the same action, so an
        # unpaid fee must never hold a link.
        CheckConstraint("payment_request_id IS NULL OR status = 'paid'",
                        name='payment_request_requires_paid'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        ForeignKey('members.id', ondelete='RESTRICT'))
    year: Mapped[int] = mapped_column(index=True)
    # Snapshots of what the member's type and its amount were when the fee was
    # created. Later changes never affect an existing fee.
    membership_type_id: Mapped[int] = mapped_column(
        ForeignKey('membership_types.id', ondelete='RESTRICT'))
    amount_ore: Mapped[int]
    status: Mapped[FeeStatus] = mapped_column(
        Enum(FeeStatus, native_enum=False, create_constraint=True, length=20,
             name='fee_status', values_callable=lambda e: [m.value for m in e]),
        default=FeeStatus.UNPAID,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey('payment_requests.id', ondelete='SET NULL'), index=True)

    member: Mapped[Member] = relationship(lazy='raise')
