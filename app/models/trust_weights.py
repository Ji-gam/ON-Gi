"""TrustWeights = REQ-F-TRS-08 신뢰 점수 가중치(w1~w4, 싱글턴 row id=1) + 변경 이력."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class TrustWeights(Base):
    __tablename__ = "trust_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    w1: Mapped[float] = mapped_column(Float, nullable=False)
    w2: Mapped[float] = mapped_column(Float, nullable=False)
    w3: Mapped[float] = mapped_column(Float, nullable=False)
    w4: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TrustWeightHistory(Base):
    """REQ-F-TRS-08 가중치 변경 이력 - 변경자·시각·이전 값."""

    __tablename__ = "trust_weight_history"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    changed_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_w1: Mapped[float] = mapped_column(Float, nullable=False)
    previous_w2: Mapped[float] = mapped_column(Float, nullable=False)
    previous_w3: Mapped[float] = mapped_column(Float, nullable=False)
    previous_w4: Mapped[float] = mapped_column(Float, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
