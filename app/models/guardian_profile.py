"""GuardianProfile = 보호자(User) 프로필 확장(REQ-F-ACC-04). auth_kit(공유 패키지) 소유인
User 모델은 직접 수정하지 않고, user_id FK로 연결된 별도 테이블에 분리한다.

거주지는 좌표가 아닌 H3 셀 문자열로만 저장한다(REQ-NF-SEC-05). 보유 태그는 MAT 하드필터
(REQ-F-MAT-03)의 선택 6종이 아직 확정되지 않아, 고정 Enum 대신 확장 가능한 코드 목록으로 둔다
(`docs/tasks/T-ACC-2.md` 가정 참고).
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class JobCategory(StrEnum):
    OFFICE_WORKER = "OFFICE_WORKER"
    SERVICE = "SERVICE"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    HEALTHCARE = "HEALTHCARE"
    EDUCATION = "EDUCATION"
    IT = "IT"
    PUBLIC_SERVANT = "PUBLIC_SERVANT"
    HOMEMAKER = "HOMEMAKER"
    FREELANCER = "FREELANCER"
    OTHER = "OTHER"


class WorkType(StrEnum):
    FULL_TIME = "FULL_TIME"
    SHIFT = "SHIFT"
    FLEXIBLE = "FLEXIBLE"
    REMOTE = "REMOTE"
    FREELANCE = "FREELANCE"
    UNEMPLOYED = "UNEMPLOYED"
    OTHER = "OTHER"


class HouseholdComposition(StrEnum):
    TWO_PARENT = "TWO_PARENT"
    SINGLE_PARENT = "SINGLE_PARENT"
    EXTENDED_FAMILY = "EXTENDED_FAMILY"
    OTHER = "OTHER"


class GuardianProfile(Base):
    __tablename__ = "guardian_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    residence_h3: Mapped[str] = mapped_column(String(15), nullable=False, index=True)
    job_category: Mapped[JobCategory] = mapped_column(
        Enum(JobCategory, values_callable=lambda e: [x.value for x in e], name="job_category_enum"), nullable=False
    )
    work_type: Mapped[WorkType] = mapped_column(
        Enum(WorkType, values_callable=lambda e: [x.value for x in e], name="work_type_enum"), nullable=False
    )
    household_composition: Mapped[HouseholdComposition] = mapped_column(
        Enum(
            HouseholdComposition,
            values_callable=lambda e: [x.value for x in e],
            name="household_composition_enum",
        ),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class GuardianTag(Base):
    """REQ-F-ACC-04 보유 태그. MAT 선택 6종 미확정이라 고정 Enum이 아닌 코드 문자열로 저장한다."""

    __tablename__ = "guardian_tags"
    __table_args__ = (UniqueConstraint("user_id", "tag_code", name="uq_guardian_tag_user_code"),)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_code: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
