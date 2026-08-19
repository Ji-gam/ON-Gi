"""COM 도메인 - 인앱 알림(REQ-F-COM-02). 웹푸시(VAPID)는 §5 결정 대기, 우선 인앱만 제공."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies import get_current_user
from app.dtos.notification_dto import NotificationResponse
from app.services.notification_service import NotificationService
from auth_kit.models import User

com_router = APIRouter(prefix="/com", tags=["com"])

Session = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@com_router.get(
    "/notifications",
    response_model=list[NotificationResponse],
    summary="내 알림 목록 조회",
    description="REQ-F-COM-02. 최신순으로 반환한다.",
)
async def list_notifications(session: Session, user: CurrentUser) -> list[NotificationResponse]:
    notifications = await NotificationService(session).list_notifications(user.id)
    return [NotificationResponse.model_validate(n) for n in notifications]


@com_router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    summary="알림 읽음 처리",
)
async def mark_notification_read(notification_id: int, session: Session, user: CurrentUser) -> NotificationResponse:
    notification = await NotificationService(session).mark_read(notification_id, user.id)
    return NotificationResponse.model_validate(notification)
