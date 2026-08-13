"""ParentingValuesProfile = 보호자(User)의 양육 가치관 진단 결과(REQ-F-ACC-07).
auth_kit(공유 패키지) 소유인 User 모델은 수정하지 않고 user_id FK로 분리한다.

온기/통제 2축 점수는 MAT 도메인(REQ-F-MAT-04)의 코사인 유사도 계산 입력값이 된다.
재진단(REQ-F-ACC-08)·자유서술 보정(REQ-F-ACC-10) 이력은 `ParentingValuesHistory`에 스냅샷으로 남긴다.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.utils.baumrind_questions import ParentingTypeLabel
from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class ParentingValuesSource(StrEnum):
    QUESTIONNAIRE = "QUESTIONNAIRE"
    NARRATIVE = "NARRATIVE"


class ParentingValuesProfile(Base):
    __tablename__ = "parenting_values_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    warmth_score: Mapped[float] = mapped_column(Float, nullable=False)
    control_score: Mapped[float] = mapped_column(Float, nullable=False)
    type_label: Mapped[ParentingTypeLabel] = mapped_column(
        Enum(ParentingTypeLabel, values_callable=lambda e: [x.value for x in e], name="parenting_type_label_enum"),
        nullable=False,
    )
    narrative: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ParentingValuesHistory(Base):
    """REQ-F-ACC-08/10 — 재진단·자유서술 제출마다 스냅샷 1행을 남긴다(변경 이력 추적)."""

    __tablename__ = "parenting_values_history"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    warmth_score: Mapped[float] = mapped_column(Float, nullable=False)
    control_score: Mapped[float] = mapped_column(Float, nullable=False)
    type_label: Mapped[ParentingTypeLabel] = mapped_column(
        Enum(ParentingTypeLabel, values_callable=lambda e: [x.value for x in e], name="parenting_type_label_enum"),
        nullable=False,
    )
    source: Mapped[ParentingValuesSource] = mapped_column(
        Enum(
            ParentingValuesSource, values_callable=lambda e: [x.value for x in e], name="parenting_values_source_enum"
        ),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
