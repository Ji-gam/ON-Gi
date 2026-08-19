"""REQ-F-COM-02. 다른 도메인 서비스가 상태 변경 시점에 호출하는 얇은 알림 생성기.
`HypothesisEventService`와 동일한 이유로 절대 커밋하지 않는다 — 호출자의 기존
트랜잭션 커밋에 함께 실려야 훅이 추가 라운드트립 없이 붙는다.
"""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.repositories.notification_repository import NotificationRepository


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NotificationRepository(session)

    def notify(
        self, user_id: int, notification_type: NotificationType, message: str, payload: dict | None = None
    ) -> None:
        self.repo.add(Notification(user_id=user_id, type=notification_type, message=message, payload=payload))

    async def list_notifications(self, user_id: int) -> list[Notification]:
        return await self.repo.list_for_user(user_id)

    async def mark_read(self, notification_id: int, user_id: int) -> Notification:
        notification = await self.repo.get(notification_id)
        if notification is None or notification.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "알림을 찾을 수 없습니다.")
        if notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            await self.session.commit()
            await self.session.refresh(notification)
        return notification
