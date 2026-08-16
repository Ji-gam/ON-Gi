"""PointHold = REQ-F-PNT-05 포인트 예치(홀드). 세션 확정 시 예상 돌봄 시간만큼 요청자의
포인트를 계정 자체에 예약해 두고(같은 계정 내 balance→held_balance 이동, 상대에게는 아직
이전되지 않음), 완료/취소/노쇼 시점에 정산·반환·몰수 중 하나로 해소한다.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class PointHoldStatus(StrEnum):
    HELD = "HELD"
    SETTLED = "SETTLED"
    RELEASED = "RELEASED"
    FORFEITED = "FORFEITED"


class PointHold(Base):
    __tablename__ = "point_holds"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    care_session_id: Mapped[int] = mapped_column(
        ForeignKey("care_sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    payer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    payee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False, doc="예약된 슬롯(30분) 수")
    status: Mapped[PointHoldStatus] = mapped_column(
        Enum(PointHoldStatus, values_callable=lambda e: [x.value for x in e], name="point_hold_status_enum"),
        nullable=False,
        default=PointHoldStatus.HELD,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
