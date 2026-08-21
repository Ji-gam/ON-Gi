"""REQ-F-COM-01. 1:1 채팅. `trust_relationships`가 이미 두 사용자 쌍의 유일 관계를 보장하므로
별도 "채팅방" 테이블을 만들지 않고 그 관계에 메시지를 붙인다(L1 이상부터 관계가 존재).
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    relationship_id: Mapped[int] = mapped_column(
        ForeignKey("trust_relationships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(1000), nullable=False)
    pii_masked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
