"""CareLog = 돌봄 일지(REQ-F-CAR-06). 세션당 1건(upsert). 대상 아동에게 알레르기 정보가
등록돼 있으면 `allergy_note` 없이는 저장이 거부된다(서비스 계층에서 검증).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CareLog(Base):
    __tablename__ = "care_logs"

    session_id: Mapped[int] = mapped_column(ForeignKey("care_sessions.id", ondelete="CASCADE"), primary_key=True)
    meal: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sleep: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mood: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    allergy_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
