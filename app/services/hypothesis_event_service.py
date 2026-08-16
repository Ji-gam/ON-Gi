"""REQ-F-ADM-04. 다른 도메인 서비스가 상태 변경 시점에 호출하는 얇은 이벤트 로거.
이 서비스는 절대 커밋하지 않는다 — 호출자의 기존 트랜잭션 커밋에 함께 실려야 훅이
추가 라운드트립 없이 붙는다."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hypothesis_event import HypothesisEvent, HypothesisEventType
from app.repositories.hypothesis_event_repository import HypothesisEventRepository


class HypothesisEventService:
    def __init__(self, session: AsyncSession):
        self.repo = HypothesisEventRepository(session)

    def log(
        self,
        event_type: HypothesisEventType,
        actor_user_id: int,
        target_user_id: int | None = None,
        payload: dict | None = None,
    ) -> None:
        self.repo.add(
            HypothesisEvent(
                event_type=event_type,
                actor_user_id=actor_user_id,
                target_user_id=target_user_id,
                payload=payload,
            )
        )
