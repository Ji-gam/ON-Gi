from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.schedule_slots import FULL_AVAILABLE_MASK, ShiftTemplate, template_masks
from app.models.work_schedule import WorkSchedule
from app.repositories.work_schedule_repository import WorkScheduleRepository
from auth_kit.models import User


class WorkScheduleService:
    """REQ-F-SCH-01/03/06. 근무 템플릿 등록은 upsert - NIGHT는 당일+익일 두 행에 걸쳐 반영."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = WorkScheduleRepository(session)

    async def _get_or_create(self, user_id: int, work_date: date) -> WorkSchedule:
        row = await self.repo.get(user_id, work_date)
        if row is None:
            row = WorkSchedule(
                user_id=user_id,
                work_date=work_date,
                slot_bitmask=FULL_AVAILABLE_MASK,
                shift_template=ShiftTemplate.OFF,
            )
            self.session.add(row)
        return row

    async def register_shift(self, user: User, work_date: date, template: ShiftTemplate) -> list[WorkSchedule]:
        today_mask, next_day_mask = template_masks(template)

        today_row = await self._get_or_create(user.id, work_date)
        today_row.slot_bitmask = today_mask
        today_row.shift_template = template
        affected = [today_row]

        if next_day_mask != FULL_AVAILABLE_MASK:
            next_day = work_date + timedelta(days=1)
            next_row = await self._get_or_create(user.id, next_day)
            next_row.slot_bitmask &= next_day_mask
            affected.append(next_row)

        await self.session.commit()
        for row in affected:
            await self.session.refresh(row)
        return affected

    async def list_range(self, user: User, start: date, end: date) -> list[WorkSchedule]:
        return await self.repo.list_range(user.id, start, end)
