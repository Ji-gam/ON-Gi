"""REQ-F-ADM-02(핵심 지표 집계)/ADM-05(아동 안전 긴급 정지). 운영자 전용 도메인.
`TrustLevelService.demote`와 동일한 패턴으로 `admin.is_admin` 여부를 서비스 계층에서 직접 검사한다.
"""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_session import CareSession, CareSessionStatus
from app.models.hypothesis_event import HypothesisEventType
from app.models.notification import NotificationType
from app.repositories.care_session_repository import CareSessionRepository
from app.repositories.hypothesis_event_repository import HypothesisEventRepository
from app.services.notification_service import NotificationService
from app.services.point_ledger_service import PointLedgerService
from auth_kit.models import User

ADMIN_ONLY_MESSAGE = "운영자만 수행할 수 있습니다."


def _require_admin(admin: User) -> None:
    if not admin.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, ADMIN_ONLY_MESSAGE)


class AdminMetricsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.event_repo = HypothesisEventRepository(session)

    async def get_core_metrics(self) -> dict[str, float]:
        total_users = await self.session.scalar(select(func.count()).select_from(User).where(~User.is_guest)) or 0
        exposed_users = await self.event_repo.count_distinct_actors_by_type(HypothesisEventType.CANDIDATE_EXPOSURE)
        candidate_availability_rate = exposed_users / total_users if total_users else 0.0

        # payload.new_level은 JSON 컬럼이라 DB 방언(SQLite/Postgres)에 안전하게 걸치려면
        # 파이썬에서 필터한다 - 이벤트 총량이 대시보드 집계 수준이라 성능상 문제 없다.
        transitions = await self.event_repo.list_by_type(HypothesisEventType.TRUST_LEVEL_TRANSITION)
        reached_l2 = sum(1 for e in transitions if (e.payload or {}).get("new_level") == "L2")
        reached_l3 = sum(1 for e in transitions if (e.payload or {}).get("new_level") == "L3")
        l2_to_l3_transition_rate = reached_l3 / reached_l2 if reached_l2 else 0.0

        requested = await self.event_repo.count_by_type(HypothesisEventType.REQUEST_CREATED)
        rematched = await self.event_repo.count_by_type(HypothesisEventType.REMATCH_REQUESTED)
        total_requests = requested + rematched
        rematch_rate = rematched / total_requests if total_requests else 0.0

        return {
            "candidate_availability_rate": candidate_availability_rate,
            "l2_to_l3_transition_rate": l2_to_l3_transition_rate,
            "rematch_rate": rematch_rate,
        }


class AdminSuspendService:
    """REQ-F-ADM-05. 진행/예정 세션(REQUESTED/CONFIRMED)을 즉시 중단시키고 상대에게 알린다.
    확정 세션의 포인트 홀드는 대상자 귀책이 아니라 안전 조치이므로 전액 반환한다."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.session_repo = CareSessionRepository(session)
        self.point_ledger_service = PointLedgerService(session)
        self.notification_service = NotificationService(session)

    async def emergency_suspend(self, admin: User, target_user_id: int, reason: str) -> list[CareSession]:
        _require_admin(admin)
        target = await self.session.get(User, target_user_id)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "대상 계정을 찾을 수 없습니다.")

        target.is_sanctioned = True
        target.sanction_reason = reason
        target.is_active = False

        stopped: list[tuple[CareSession, bool]] = []
        for care_session in await self.session_repo.list_for_user(target_user_id):
            if care_session.status not in (CareSessionStatus.REQUESTED, CareSessionStatus.CONFIRMED):
                continue
            was_confirmed = care_session.status == CareSessionStatus.CONFIRMED
            care_session.status = CareSessionStatus.CANCELLED
            care_session.cancelled_at = datetime.now(UTC)
            care_session.cancel_reason = f"관리자 긴급 정지: {reason}"
            counterparty_id = (
                care_session.provider_id if target_user_id == care_session.requester_id else care_session.requester_id
            )
            self.notification_service.notify(
                counterparty_id,
                NotificationType.SESSION_CANCELLED,
                "상대 계정 안전 문제로 돌봄 세션이 중단됐어요.",
                payload={"session_id": care_session.id},
            )
            stopped.append((care_session, was_confirmed))

        await self.session.commit()

        for care_session, was_confirmed in stopped:
            await self.session.refresh(care_session)
            if was_confirmed:
                await self.point_ledger_service.resolve_hold_on_cancel(care_session, past_deadline=False)

        return [care_session for care_session, _ in stopped]
