"""CareSession = 돌봄 요청 생성·수락·거절(REQ-F-CAR-01/02). 요청자(User)가 제공자(User)에게
특정 날짜의 48슬롯 구간(work_schedule과 동일 단위)을 요청하고, 제공자가 수락/거절한다.
수락 시 신뢰 등급 L1 전이(REQ-F-MAT-07)는 T-TRS-2 범위라 이 모델에는 관련 컬럼을 두지 않는다.
"""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, Integer, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class CareSessionStatus(StrEnum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class CareSession(Base):
    __tablename__ = "care_sessions"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    care_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    end_slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[CareSessionStatus] = mapped_column(
        Enum(CareSessionStatus, values_callable=lambda e: [x.value for x in e], name="care_session_status_enum"),
        nullable=False,
        default=CareSessionStatus.REQUESTED,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
