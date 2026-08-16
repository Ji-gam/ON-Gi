"""REQ-F-ADM-04. 가설 검증(상보 후보 보유율/L2→L3 전이율/재매칭률 등)에 쓰일 사용자 행동
이벤트 로그. 각 도메인 서비스가 상태 변경 시점에 한 행씩 남기며, 이 테이블 자체는 별도
트랜잭션을 열지 않고 호출자의 기존 커밋에 함께 실린다(`app/services/hypothesis_event_service.py`).
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class HypothesisEventType(StrEnum):
    CANDIDATE_EXPOSURE = "CANDIDATE_EXPOSURE"
    REQUEST_CREATED = "REQUEST_CREATED"
    REQUEST_ACCEPTED = "REQUEST_ACCEPTED"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    TRUST_LEVEL_TRANSITION = "TRUST_LEVEL_TRANSITION"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    REMATCH_REQUESTED = "REMATCH_REQUESTED"


class HypothesisEvent(Base):
    __tablename__ = "hypothesis_events"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    event_type: Mapped[HypothesisEventType] = mapped_column(
        Enum(HypothesisEventType, native_enum=False, length=30), nullable=False, index=True
    )
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
