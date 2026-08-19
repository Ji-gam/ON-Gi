"""REQ-F-COM-02. 인앱 알림. 웹푸시(VAPID)는 §5 결정 대기 항목이라 이 테이블은
발송 채널과 무관하게 "무슨 일이 있었는지"만 쌓고, 조회 시점에 화면이 읽는다.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class NotificationType(StrEnum):
    REQUEST_CREATED = "REQUEST_CREATED"
    REQUEST_ACCEPTED = "REQUEST_ACCEPTED"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_CANCELLED = "SESSION_CANCELLED"
    NO_SHOW_REPORTED = "NO_SHOW_REPORTED"
    TRUST_LEVEL_TRANSITION = "TRUST_LEVEL_TRANSITION"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, native_enum=False, length=30), nullable=False)
    message: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
