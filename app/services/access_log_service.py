"""REQ-F-ADM-03. 호출자가 이미 연 트랜잭션에 로그 1건을 얹는 얇은 로거. 절대 커밋하지 않는다."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access_log import AccessAction, AccessLog
from app.repositories.access_log_repository import AccessLogRepository


class AccessLogService:
    def __init__(self, session: AsyncSession):
        self.repo = AccessLogRepository(session)

    def log(self, actor_user_id: int, target_child_id: int, action: AccessAction) -> None:
        self.repo.add(AccessLog(actor_user_id=actor_user_id, target_child_id=target_child_id, action=action))
