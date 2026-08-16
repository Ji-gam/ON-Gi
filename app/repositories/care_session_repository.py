from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_session import CareSession


class CareSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, session_id: int) -> CareSession | None:
        return await self.session.get(CareSession, session_id)

    def add(self, care_session: CareSession) -> None:
        self.session.add(care_session)

    async def has_completed_pairing(self, user_a_id: int, user_b_id: int) -> bool:
        """REQ-F-ADM-04 재요청(REMATCH_REQUESTED) 판정: 두 사용자 사이에 체크아웃까지
        완료된(=완료 이력이 있는) 세션이 이전에 존재하는지 확인한다(REQ-F-MAT-09 재요청 개념)."""
        pair = or_(
            and_(CareSession.requester_id == user_a_id, CareSession.provider_id == user_b_id),
            and_(CareSession.requester_id == user_b_id, CareSession.provider_id == user_a_id),
        )
        result = await self.session.execute(select(exists().where(pair, CareSession.checkout_at.is_not(None))))
        return bool(result.scalar())
