"""JointCareSession = 공개 장소 공동육아 일정(REQ-F-TRS-02). GPS 체크인 없이 "장소 선택 +
양측 완료 확인"만으로 1회 집계한다는 점에서 `care_sessions`(단독 위탁)와 별개 모델이다.
"""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class JointCareSessionStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"


class JointCareSession(Base):
    __tablename__ = "joint_care_sessions"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    place: Mapped[str] = mapped_column(String(100), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    confirmed_by_initiator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_by_partner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[JointCareSessionStatus] = mapped_column(
        Enum(JointCareSessionStatus, native_enum=False, length=10),
        nullable=False,
        default=JointCareSessionStatus.SCHEDULED,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
