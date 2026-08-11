from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_log import CareLog


class CareLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, session_id: int) -> CareLog | None:
        return await self.session.get(CareLog, session_id)

    def add(self, care_log: CareLog) -> None:
        self.session.add(care_log)
