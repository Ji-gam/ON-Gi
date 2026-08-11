"""TrustRelationship = 두 사용자 사이의 신뢰 등급 상태머신(REQ-F-TRS-01). L1(매칭)→L2(공동육아
진행 중)→L3(단독 위탁 해금) 순으로만 시스템이 자동 승급시키고, 강등은 운영자만 수동으로
수행한다(docs/tasks/T-TRS-2.md 가정 §5).
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class TrustLevel(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class TrustRelationship(Base):
    __tablename__ = "trust_relationships"
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id", name="uq_trust_relationship_pair"),)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_b_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    level: Mapped[TrustLevel] = mapped_column(
        Enum(TrustLevel, native_enum=False, length=2), nullable=False, default=TrustLevel.L1
    )
    joint_session_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TrustLevelHistory(Base):
    """REQ-F-TRS-01 역방향 전이(강등) 및 승급 이력."""

    __tablename__ = "trust_level_history"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    relationship_id: Mapped[int] = mapped_column(
        ForeignKey("trust_relationships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_level: Mapped[TrustLevel] = mapped_column(Enum(TrustLevel, native_enum=False, length=2), nullable=False)
    new_level: Mapped[TrustLevel] = mapped_column(Enum(TrustLevel, native_enum=False, length=2), nullable=False)
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
