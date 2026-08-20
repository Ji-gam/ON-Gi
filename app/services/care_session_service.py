"""REQ-F-CAR-01/02/03/05. 돌봄 요청 생성은 제공자가 상보 가능한 구간(제공자 가용+요청자
불가)만 허용한다(T-MAT-1과 동일한 "근무표 미등록 날짜=풀가용" 규칙 재사용). 수락/거절/체크인/
체크아웃은 요청받은 제공자 본인만 수행 가능하다. 체크인은 GPS 원본 좌표를 저장하지 않고
약속 장소(`meeting_h3`)와의 거리(m)만 저장한다(REQ-NF-SEC-05 원칙 준용).
"""

import math
from datetime import UTC, date, datetime, timedelta

import h3
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.schedule_slots import FULL_AVAILABLE_MASK
from app.models.care_session import CareSession, CareSessionStatus
from app.models.hypothesis_event import HypothesisEventType
from app.models.notification import NotificationType
from app.repositories.care_evaluation_repository import CareEvaluationRepository
from app.repositories.care_session_repository import CareSessionRepository
from app.repositories.child_repository import ChildRepository
from app.repositories.work_schedule_repository import WorkScheduleRepository
from app.services.hypothesis_event_service import HypothesisEventService
from app.services.notification_service import NotificationService
from app.services.point_ledger_service import PointLedgerService
from app.services.trust_level_service import TrustLevelService
from auth_kit.models import User

PENDING_EVALUATION_MESSAGE = "완료된 세션에 대한 평가를 먼저 제출하세요."

CHECKIN_RADIUS_M = 200.0  # 요구사항정의서에 수치 미명시 - 임의 가정(REQ-F-CAR-03)
CANCELLATION_DEADLINE_HOURS = 2  # 요구사항정의서에 "취소 마감 시각" 수치 미명시 - 임의 가정(REQ-F-PNT-05)


def _range_bits(start_slot: int, end_slot: int) -> int:
    return ((1 << (end_slot - start_slot)) - 1) << start_slot


def _aware(value: datetime) -> datetime:
    """SQLite는 timezone-aware 컬럼도 naive datetime으로 되돌려줄 수 있어 UTC로 보정한다."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _scheduled_start(care_session: CareSession) -> datetime:
    return datetime.combine(care_session.care_date, datetime.min.time(), tzinfo=UTC) + timedelta(
        minutes=care_session.start_slot * 30
    )


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
        self.evaluation_repo = CareEvaluationRepository(session)
        self.trust_level_service = TrustLevelService(session)
        self.point_ledger_service = PointLedgerService(session)
        self.event_service = HypothesisEventService(session)
        self.notification_service = NotificationService(session)

    async def create_request(
        self,
        requester: User,
        provider_id: int,
        child_id: int,
        meeting_h3: str,
        care_date: date,
        start_slot: int,
        end_slot: int,
        is_solo: bool = False,
    ) -> CareSession:
        if not (0 <= start_slot < end_slot <= 48):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "요청 구간이 올바르지 않습니다.")

        if await self.evaluation_repo.has_pending_evaluation(requester.id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, PENDING_EVALUATION_MESSAGE)

        if is_solo:
            await self.trust_level_service.require_l3(requester.id, provider_id)

        await self.point_ledger_service.ensure_can_request(requester.id)

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

        if await self.repo.has_overlap(requester.id, care_date, start_slot, end_slot) or await self.repo.has_overlap(
            provider_id, care_date, start_slot, end_slot
        ):
            raise HTTPException(status.HTTP_409_CONFLICT, "요청자 또는 제공자가 같은 시간에 처리 중인 요청이 있습니다.")

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
        is_rematch = await self.repo.has_completed_pairing(requester.id, provider_id)
        self.repo.add(care_session)
        self.event_service.log(
            HypothesisEventType.REMATCH_REQUESTED if is_rematch else HypothesisEventType.REQUEST_CREATED,
            requester.id,
            provider_id,
            payload={"care_date": care_date.isoformat(), "is_solo": is_solo},
        )
        self.notification_service.notify(
            provider_id,
            NotificationType.REQUEST_CREATED,
            "새 돌봄 요청이 도착했어요.",
            payload={"care_date": care_date.isoformat()},
        )
        await self.session.commit()
        await self.session.refresh(care_session)
        return care_session

    async def list_mine(self, user: User) -> list[CareSession]:
        return await self.repo.list_for_user(user.id)

    async def get_mine(self, session_id: int, user: User) -> CareSession:
        care_session = await self.repo.get(session_id)
        if care_session is None or user.id not in (care_session.requester_id, care_session.provider_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
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
        if await self.evaluation_repo.has_pending_evaluation(provider.id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, PENDING_EVALUATION_MESSAGE)
        care_session.status = CareSessionStatus.CONFIRMED
        await self.trust_level_service.grant_l1(care_session.requester_id, care_session.provider_id)
        self.event_service.log(
            HypothesisEventType.REQUEST_ACCEPTED,
            provider.id,
            care_session.requester_id,
            payload={"session_id": session_id},
        )
        self.notification_service.notify(
            care_session.requester_id,
            NotificationType.REQUEST_ACCEPTED,
            "돌봄 요청이 수락됐어요.",
            payload={"session_id": session_id},
        )
        await self.session.commit()
        await self.session.refresh(care_session)

        await self.point_ledger_service.create_hold(care_session)
        return care_session

    async def reject(self, session_id: int, provider: User) -> CareSession:
        care_session = await self._get_requested_session(session_id, provider)
        care_session.status = CareSessionStatus.REJECTED
        self.event_service.log(
            HypothesisEventType.REQUEST_REJECTED,
            provider.id,
            care_session.requester_id,
            payload={"session_id": session_id},
        )
        self.notification_service.notify(
            care_session.requester_id,
            NotificationType.REQUEST_REJECTED,
            "돌봄 요청이 거절됐어요.",
            payload={"session_id": session_id},
        )
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
        await self.session.commit()
        await self.session.refresh(care_session)

        await self.point_ledger_service.settle_care_session(care_session)
        self.event_service.log(
            HypothesisEventType.SESSION_COMPLETED,
            provider.id,
            care_session.requester_id,
            payload={"session_id": session_id, "actual_minutes": care_session.actual_minutes},
        )
        self.notification_service.notify(
            care_session.requester_id,
            NotificationType.SESSION_COMPLETED,
            "돌봄이 완료됐어요.",
            payload={"session_id": session_id},
        )
        await self.session.commit()
        return care_session

    async def _get_cancellable_session(self, session_id: int, actor: User) -> CareSession:
        care_session = await self.repo.get(session_id)
        if care_session is None or actor.id not in (care_session.requester_id, care_session.provider_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
        if care_session.status not in (CareSessionStatus.REQUESTED, CareSessionStatus.CONFIRMED):
            raise HTTPException(status.HTTP_409_CONFLICT, "취소할 수 없는 상태입니다.")
        if care_session.checkin_at is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "체크인 이후에는 취소할 수 없습니다.")
        return care_session

    async def cancel(self, session_id: int, actor: User, reason: str | None) -> CareSession:
        """REQ-F-CAR-07/PNT-05. 요청자·제공자 모두 취소 가능. CONFIRMED 상태(홀드 존재)에서
        취소 마감 시각(세션 시작 `CANCELLATION_DEADLINE_HOURS`시간 전) 이후 취소는 취소한
        본인 귀책으로 기록되고 홀드가 상대에게 이전된다."""
        care_session = await self._get_cancellable_session(session_id, actor)
        was_confirmed = care_session.status == CareSessionStatus.CONFIRMED
        now = datetime.now(UTC)
        past_deadline = now > _scheduled_start(care_session) - timedelta(hours=CANCELLATION_DEADLINE_HOURS)

        care_session.status = CareSessionStatus.CANCELLED
        care_session.cancelled_at = now
        care_session.cancel_reason = reason
        if was_confirmed and past_deadline:
            care_session.at_fault_user_id = actor.id
        counterparty_id = (
            care_session.provider_id if actor.id == care_session.requester_id else care_session.requester_id
        )
        self.notification_service.notify(
            counterparty_id,
            NotificationType.SESSION_CANCELLED,
            "돌봄 세션이 취소됐어요.",
            payload={"session_id": session_id},
        )
        await self.session.commit()
        await self.session.refresh(care_session)

        if was_confirmed:
            await self.point_ledger_service.resolve_hold_on_cancel(care_session, past_deadline)
        return care_session

    async def report_no_show(self, session_id: int, reporter: User, reason: str | None) -> CareSession:
        """REQ-F-CAR-07. 세션 종료 시각이 지나도록 체크인이 없으면 상대(체크인 없는 쪽의
        반대 당사자)가 무단 불참을 신고할 수 있다. 신고자의 반대편이 귀책자로 기록되고,
        요청자 귀책이면 홀드가 제공자에게 이전되며, 제공자 귀책이면 홀드가 요청자에게
        반환된다(신뢰 점수 반영은 `TrustScoreService`가 `at_fault_user_id`를 조회)."""
        care_session = await self.repo.get(session_id)
        if care_session is None or reporter.id not in (care_session.requester_id, care_session.provider_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
        if care_session.status != CareSessionStatus.CONFIRMED:
            raise HTTPException(status.HTTP_409_CONFLICT, "확정된 세션만 노쇼 처리할 수 있습니다.")
        if care_session.checkin_at is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 체크인한 세션은 노쇼로 처리할 수 없습니다.")

        scheduled_end = _scheduled_start(care_session) + timedelta(
            minutes=(care_session.end_slot - care_session.start_slot) * 30
        )
        now = datetime.now(UTC)
        if now < scheduled_end:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "세션 종료 시각 이전에는 노쇼 처리할 수 없습니다.")

        at_fault_id = (
            care_session.provider_id if reporter.id == care_session.requester_id else care_session.requester_id
        )

        care_session.status = CareSessionStatus.NO_SHOW
        care_session.cancelled_at = now
        care_session.cancel_reason = reason
        care_session.at_fault_user_id = at_fault_id
        self.notification_service.notify(
            at_fault_id,
            NotificationType.NO_SHOW_REPORTED,
            "무단 불참으로 신고됐어요.",
            payload={"session_id": session_id},
        )
        await self.session.commit()
        await self.session.refresh(care_session)

        await self.point_ledger_service.resolve_hold_on_no_show(care_session)
        return care_session
