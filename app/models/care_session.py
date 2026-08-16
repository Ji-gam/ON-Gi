"""CareSession = 돌봄 요청 생성·수락·거절(REQ-F-CAR-01/02) + 체크인/체크아웃(REQ-F-CAR-03/05).
요청자(User)가 제공자(User)에게 특정 날짜의 48슬롯 구간(work_schedule과 동일 단위)·대상 아동·
약속 장소를 지정해 요청하고, 제공자가 수락/거절한다. 체크인은 GPS 좌표를 저장하지 않고 계산된
거리(m)만 저장한다(REQ-NF-SEC-05 원칙 준용). 수락 시 신뢰 등급 L1 전이(REQ-F-MAT-07)는
T-TRS-2 범위라 이 모델에는 관련 컬럼을 두지 않는다.
"""

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class CareSessionStatus(StrEnum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class CareSession(Base):
    __tablename__ = "care_sessions"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_h3: Mapped[str] = mapped_column(String(15), nullable=False)
    care_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    end_slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[CareSessionStatus] = mapped_column(
        Enum(CareSessionStatus, values_callable=lambda e: [x.value for x in e], name="care_session_status_enum"),
        nullable=False,
        default=CareSessionStatus.REQUESTED,
    )

    checkin_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkin_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    checkin_out_of_range: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checkin_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    checkout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    at_fault_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        doc="REQ-F-CAR-07 취소 마감 이후 취소/노쇼 시 귀책 당사자",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
