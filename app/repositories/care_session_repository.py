from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_session import CareSession


class CareSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, session_id: int) -> CareSession | None:
        return await self.session.get(CareSession, session_id)

    def add(self, care_session: CareSession) -> None:
        self.session.add(care_session)
