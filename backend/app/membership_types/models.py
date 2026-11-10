from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MembershipType(Base):
    __tablename__ = 'membership_types'
    __table_args__ = (
        CheckConstraint('amount_ore > 0', name='amount_ore_positive'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    amount_ore: Mapped[int]
