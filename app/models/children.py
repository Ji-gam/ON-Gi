"""Child = 아동(REQ-F-ACC-05/06). 로그인 계정 없음 - 보호자(User)가 user_id로 직접 소유한다.

알레르기·지병·투약 등 민감정보는 일반 정보와 물리적으로 분리된 테이블에 컬럼단위 암호화로
저장한다(REQ-NF-SEC-01, REQ-NF-DAT-02) - 매칭(MAT)의 완화불가 하드필터 입력값이 된다.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from security_kit.crypto import EncryptedStr

_PK = BigInteger().with_variant(Integer, "sqlite")


class ChildGender(StrEnum):
    MALE = "M"
    FEMALE = "F"


class Child(Base):
    __tablename__ = "children"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    months_old: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[ChildGender] = mapped_column(
        Enum(ChildGender, values_callable=lambda e: [x.value for x in e], name="child_gender_enum"), nullable=False
    )
    temperament_memo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    sensitive: Mapped["ChildSensitiveInfo | None"] = relationship(
        back_populates="child", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )

    @property
    def has_sensitive_info(self) -> bool:
        return self.sensitive is not None and self.sensitive.has_any


class ChildSensitiveInfo(Base):
    """REQ-F-ACC-06. `children`과 분리된 테이블 - PII/민감정보 분리 원칙(CODING_RULES.md §12)."""

    __tablename__ = "children_sensitive"

    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), primary_key=True)
    allergies: Mapped[str | None] = mapped_column(EncryptedStr, nullable=True)
    conditions: Mapped[str | None] = mapped_column(EncryptedStr, nullable=True)
    medications: Mapped[str | None] = mapped_column(EncryptedStr, nullable=True)

    child: Mapped[Child] = relationship(back_populates="sensitive")

    @property
    def has_any(self) -> bool:
        return bool(self.allergies or self.conditions or self.medications)
