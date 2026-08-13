"""WorkSchedule = 보호자(User)의 날짜별 근무 일정(REQ-F-SCH-01/03/06). 30분 단위 48슬롯
비트마스크로 저장한다 - MAT 도메인(REQ-F-MAT-01 상보 시간 계산)의 입력값이 된다.
"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base

_PK = BigInteger().with_variant(Integer, "sqlite")


class WorkSchedule(Base):
    __tablename__ = "work_schedules"
    __table_args__ = (UniqueConstraint("user_id", "work_date", name="uq_work_schedule_user_date"),)

    id: Mapped[int] = mapped_column(_PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)

    slot_bitmask: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shift_template: Mapped[ShiftTemplate] = mapped_column(
        Enum(ShiftTemplate, values_callable=lambda e: [x.value for x in e], name="shift_template_enum"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
