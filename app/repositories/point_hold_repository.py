from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.point_hold import PointHold


class PointHoldRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, hold: PointHold) -> None:
        self.session.add(hold)

    async def get_by_care_session(self, care_session_id: int) -> PointHold | None:
        result = await self.session.execute(select(PointHold).where(PointHold.care_session_id == care_session_id))
        return result.scalar_one_or_none()
