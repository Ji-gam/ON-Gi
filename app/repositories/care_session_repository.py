from datetime import date

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_session import CareSession, CareSessionStatus

_ACTIVE_STATUSES = (CareSessionStatus.REQUESTED, CareSessionStatus.CONFIRMED)


class CareSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, session_id: int) -> CareSession | None:
        return await self.session.get(CareSession, session_id)

    def add(self, care_session: CareSession) -> None:
        self.session.add(care_session)

    async def list_for_user(self, user_id: int) -> list[CareSession]:
        """세션 목록 화면(SCR-16)용 — 요청자·제공자 어느 쪽이든 본인 관여 세션을 최신순으로."""
        stmt = (
            select(CareSession)
            .where(or_(CareSession.requester_id == user_id, CareSession.provider_id == user_id))
            .order_by(CareSession.care_date.desc(), CareSession.id.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def has_overlap(self, user_id: int, care_date: date, start_slot: int, end_slot: int) -> bool:
        """REQ-F-CAR-01 이중 요청 방지: 요청자·제공자 어느 쪽이든 같은 날 처리 중인(REQUESTED/
        CONFIRMED) 세션과 시간이 겹치면 새 요청을 막는다. 거절·취소·노쇼된 세션은 겹침에서 제외."""
        overlap = and_(CareSession.start_slot < end_slot, CareSession.end_slot > start_slot)
        stmt = select(
            exists().where(
                or_(CareSession.requester_id == user_id, CareSession.provider_id == user_id),
                CareSession.care_date == care_date,
                CareSession.status.in_(_ACTIVE_STATUSES),
                overlap,
            )
        )
        result = await self.session.execute(stmt)
        return bool(result.scalar())

    async def has_completed_pairing(self, user_a_id: int, user_b_id: int) -> bool:
        """REQ-F-ADM-04 재요청(REMATCH_REQUESTED) 판정: 두 사용자 사이에 체크아웃까지
        완료된(=완료 이력이 있는) 세션이 이전에 존재하는지 확인한다(REQ-F-MAT-09 재요청 개념)."""
        pair = or_(
            and_(CareSession.requester_id == user_a_id, CareSession.provider_id == user_b_id),
            and_(CareSession.requester_id == user_b_id, CareSession.provider_id == user_a_id),
        )
        result = await self.session.execute(select(exists().where(pair, CareSession.checkout_at.is_not(None))))
        return bool(result.scalar())
