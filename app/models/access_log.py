"""REQ-F-ADM-03. 아동 민감정보 조회·수정 시 사용자·시각·대상·행위를 남기는 로그.
`HypothesisEventService`와 동일하게 별도 트랜잭션을 열지 않고 호출자의 커밋에 얹힌다.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class AccessAction(StrEnum):
    VIEW = "VIEW"
    EDIT = "EDIT"


class AccessLog(Base):
    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_child_id: Mapped[int] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[AccessAction] = mapped_column(Enum(AccessAction, native_enum=False, length=10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
