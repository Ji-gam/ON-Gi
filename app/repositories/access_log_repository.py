from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access_log import AccessLog


class AccessLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, log: AccessLog) -> None:
        self.session.add(log)
