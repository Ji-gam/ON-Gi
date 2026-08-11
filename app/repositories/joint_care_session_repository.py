from sqlalchemy.ext.asyncio import AsyncSession

from app.models.joint_care_session import JointCareSession


class JointCareSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, joint_session_id: int) -> JointCareSession | None:
        return await self.session.get(JointCareSession, joint_session_id)

    def add(self, joint_session: JointCareSession) -> None:
        self.session.add(joint_session)
