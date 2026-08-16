"""PointAccount = 사용자별 포인트 잔액(REQ-F-PNT-04). 회원가입 훅이 아니라 최초 조회 시
시드 포인트로 지연 생성한다(auth_kit은 금지 경로, docs/tasks/T-PNT-1.md 가정 §1).
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SEED_POINTS = 12  # 6시간 상당(30분=1슬롯) - 수치 미명시, 가정(docs/tasks/T-PNT-1.md)
NEGATIVE_BALANCE_LIMIT = -12  # 시드와 동일한 한도까지 마이너스 허용 후 차단


class PointAccount(Base):
    __tablename__ = "point_accounts"

    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=SEED_POINTS)
    held_balance: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, doc="REQ-F-PNT-05 홀드 중인 포인트(예약, balance에서 분리 보관)"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
