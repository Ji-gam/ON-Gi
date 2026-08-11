"""REQ-F-CAR-01/02. 돌봄 요청 생성은 제공자가 상보 가능한 구간(제공자 가용+요청자 불가)만
허용한다(T-MAT-1과 동일한 "근무표 미등록 날짜=풀가용" 규칙 재사용). 수락/거절은 요청받은
제공자 본인만 수행 가능하다.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.schedule_slots import FULL_AVAILABLE_MASK
from app.models.care_session import CareSession, CareSessionStatus
from app.repositories.care_session_repository import CareSessionRepository
from app.repositories.work_schedule_repository import WorkScheduleRepository
from auth_kit.models import User


def _range_bits(start_slot: int, end_slot: int) -> int:
    return ((1 << (end_slot - start_slot)) - 1) << start_slot


class CareSessionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CareSessionRepository(session)
        self.schedule_repo = WorkScheduleRepository(session)

    async def create_request(
        self, requester: User, provider_id: int, care_date: date, start_slot: int, end_slot: int
    ) -> CareSession:
        if not (0 <= start_slot < end_slot <= 48):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "요청 구간이 올바르지 않습니다.")

        requester_schedule = await self.schedule_repo.get(requester.id, care_date)
        provider_schedule = await self.schedule_repo.get(provider_id, care_date)
        requester_mask = requester_schedule.slot_bitmask if requester_schedule else FULL_AVAILABLE_MASK
        provider_mask = provider_schedule.slot_bitmask if provider_schedule else FULL_AVAILABLE_MASK

        requested_range = _range_bits(start_slot, end_slot)
        complementary_mask = (~requester_mask) & provider_mask & FULL_AVAILABLE_MASK
        if requested_range & ~complementary_mask:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "상보 가능 시간대가 아닙니다.")

        care_session = CareSession(
            requester_id=requester.id,
            provider_id=provider_id,
            care_date=care_date,
            start_slot=start_slot,
            end_slot=end_slot,
            status=CareSessionStatus.REQUESTED,
        )
        self.repo.add(care_session)
        await self.session.commit()
        await self.session.refresh(care_session)
        return care_session

    async def _get_requested_session(self, session_id: int, provider: User) -> CareSession:
        care_session = await self.repo.get(session_id)
        if care_session is None or care_session.provider_id != provider.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "요청을 찾을 수 없습니다.")
        if care_session.status != CareSessionStatus.REQUESTED:
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 처리된 요청입니다.")
        return care_session

    async def accept(self, session_id: int, provider: User) -> CareSession:
        care_session = await self._get_requested_session(session_id, provider)
        care_session.status = CareSessionStatus.CONFIRMED
        # TODO(T-CAR-1→T-TRS-2): 수락 시 양측 신뢰 등급 L1 전이(REQ-F-MAT-07)는 TRS 상태머신 완성 후 연결
        await self.session.commit()
        await self.session.refresh(care_session)
        return care_session

    async def reject(self, session_id: int, provider: User) -> CareSession:
        care_session = await self._get_requested_session(session_id, provider)
        care_session.status = CareSessionStatus.REJECTED
        await self.session.commit()
        await self.session.refresh(care_session)
        return care_session
