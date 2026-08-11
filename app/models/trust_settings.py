"""TrustSettings = 사용자별 L2→L3 해금에 필요한 공동육아 완료 횟수(REQ-F-TRS-03). 기본 3회,
하한선 1회."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

DEFAULT_REQUIRED_JOINT_COUNT = 3
MIN_REQUIRED_JOINT_COUNT = 1


class TrustSettings(Base):
    __tablename__ = "trust_settings"

    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    required_joint_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=DEFAULT_REQUIRED_JOINT_COUNT
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
