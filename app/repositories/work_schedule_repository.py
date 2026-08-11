from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_schedule import WorkSchedule


class WorkScheduleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int, work_date: date) -> WorkSchedule | None:
        result = await self.session.execute(
            select(WorkSchedule).where(WorkSchedule.user_id == user_id, WorkSchedule.work_date == work_date)
        )
        return result.scalar_one_or_none()

    async def list_range(self, user_id: int, start: date, end: date) -> list[WorkSchedule]:
        result = await self.session.execute(
            select(WorkSchedule)
            .where(WorkSchedule.user_id == user_id, WorkSchedule.work_date.between(start, end))
            .order_by(WorkSchedule.work_date)
        )
        return list(result.scalars().all())
