"""REQ-F-CAR-01/02/03/05. 돌봄 요청 생성은 제공자가 상보 가능한 구간(제공자 가용+요청자
불가)만 허용한다(T-MAT-1과 동일한 "근무표 미등록 날짜=풀가용" 규칙 재사용). 수락/거절/체크인/
체크아웃은 요청받은 제공자 본인만 수행 가능하다. 체크인은 GPS 원본 좌표를 저장하지 않고
약속 장소(`meeting_h3`)와의 거리(m)만 저장한다(REQ-NF-SEC-05 원칙 준용).
"""

import math
from datetime import UTC, date, datetime

import h3
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.schedule_slots import FULL_AVAILABLE_MASK
from app.models.care_session import CareSession, CareSessionStatus
from app.repositories.care_session_repository import CareSessionRepository
from app.repositories.child_repository import ChildRepository
from app.repositories.work_schedule_repository import WorkScheduleRepository
from auth_kit.models import User

CHECKIN_RADIUS_M = 200.0  # 요구사항정의서에 수치 미명시 - 임의 가정(REQ-F-CAR-03)


def _range_bits(start_slot: int, end_slot: int) -> int:
    return ((1 << (end_slot - start_slot)) - 1) << start_slot


def _aware(value: datetime) -> datetime:
    """SQLite는 timezone-aware 컬럼도 naive datetime으로 되돌려줄 수 있어 UTC로 보정한다."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class CareSessionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CareSessionRepository(session)
        self.schedule_repo = WorkScheduleRepository(session)
        self.child_repo = ChildRepository(session)

    async def create_request(
        self,
        requester: User,
        provider_id: int,
        child_id: int,
        meeting_h3: str,
        care_date: date,
        start_slot: int,
        end_slot: int,
    ) -> CareSession:
        if not (0 <= start_slot < end_slot <= 48):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "요청 구간이 올바르지 않습니다.")

        child = await self.child_repo.get(child_id)
        if child is None or child.user_id != requester.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "본인 아동만 지정할 수 있습니다.")

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
            child_id=child_id,
            meeting_h3=meeting_h3,
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

    async def _get_confirmed_session(self, session_id: int, provider: User) -> CareSession:
        care_session = await self.repo.get(session_id)
        if care_session is None or care_session.provider_id != provider.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
        if care_session.status != CareSessionStatus.CONFIRMED:
            raise HTTPException(status.HTTP_409_CONFLICT, "확정되지 않은 세션입니다.")
        return care_session

    async def checkin(self, session_id: int, provider: User, lat: float, lng: float, reason: str | None) -> CareSession:
        care_session = await self._get_confirmed_session(session_id, provider)
        if care_session.checkin_at is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 체크인했습니다.")

        meeting_lat, meeting_lng = h3.cell_to_latlng(care_session.meeting_h3)
        distance_m = _haversine_m(meeting_lat, meeting_lng, lat, lng)
        out_of_range = distance_m > CHECKIN_RADIUS_M
        if out_of_range and not reason:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "반경 밖 체크인은 사유 입력이 필요합니다.")

        care_session.checkin_at = datetime.now(UTC)
        care_session.checkin_distance_m = distance_m
        care_session.checkin_out_of_range = out_of_range
        care_session.checkin_reason = reason
        await self.session.commit()
        await self.session.refresh(care_session)
        return care_session

    async def checkout(self, session_id: int, provider: User) -> CareSession:
        care_session = await self._get_confirmed_session(session_id, provider)
        if care_session.checkin_at is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "체크인 먼저 필요합니다.")
        if care_session.checkout_at is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 체크아웃했습니다.")

        checkout_at = datetime.now(UTC)
        care_session.checkout_at = checkout_at
        care_session.actual_minutes = int((checkout_at - _aware(care_session.checkin_at)).total_seconds() // 60)
        # TODO(T-CAR-2→T-PNT-1): actual_minutes를 포인트 정산 근거로 연결
        await self.session.commit()
        await self.session.refresh(care_session)
        return care_session
