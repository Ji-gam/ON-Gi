"""CareEvaluation = 돌봄 종료 후 상호 평가(REQ-F-TRS-05). 세션당 평가자 1인 1회. 태그는
`guardian_tags`와 동일하게 확장 가능한 코드 문자열로 별도 테이블에 저장한다.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class CareEvaluation(Base):
    __tablename__ = "care_evaluations"
    __table_args__ = (UniqueConstraint("session_id", "evaluator_id", name="uq_care_evaluation_session_evaluator"),)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("care_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evaluator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    evaluatee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CareEvaluationTag(Base):
    """REQ-F-TRS-05 평가 태그(시간 준수/소통 원활/안전 배려 등)."""

    __tablename__ = "care_evaluation_tags"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("care_evaluations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_code: Mapped[str] = mapped_column(String(50), nullable=False)
