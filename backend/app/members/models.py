from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.membership_types.models import MembershipType


class Member(Base):
    __tablename__ = 'members'

    id: Mapped[int] = mapped_column(primary_key=True)
    member_number: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(60), index=True)
    membership_type_id: Mapped[int] = mapped_column(
        ForeignKey('membership_types.id', ondelete='RESTRICT'), index=True)

    membership_type: Mapped[MembershipType] = relationship(lazy='raise')
