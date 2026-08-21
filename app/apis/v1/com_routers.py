"""COM 도메인 - 인앱 알림(REQ-F-COM-02) + 1:1 채팅(REQ-F-COM-01). 웹푸시(VAPID)는 §5 결정 대기,
우선 인앱만 제공."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies import get_current_user
from app.dtos.chat_dto import MessageResponse, MessageSendRequest
from app.dtos.notification_dto import NotificationResponse
from app.services.chat_service import ChatService
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


@com_router.post(
    "/chats/{partner_id}/messages",
    response_model=MessageResponse,
    summary="1:1 채팅 메시지 전송",
    description="REQ-F-COM-01. 상대와 L1 이상 관계일 때만 전송 가능. "
    "휴대폰 번호 형식이 감지되면 마스킹되고 `pii_masked=true`로 경고를 알린다.",
    responses={403: {"description": "L1 이상 매칭 관계가 없음"}},
)
async def send_message(
    session: Session, user: CurrentUser, partner_id: int, request: MessageSendRequest
) -> MessageResponse:
    message = await ChatService(session).send_message(user, partner_id, request.content)
    return MessageResponse.model_validate(message)


@com_router.get(
    "/chats/{partner_id}/messages",
    response_model=list[MessageResponse],
    summary="1:1 채팅 메시지 목록",
    description="REQ-F-COM-01. 상대와 L1 이상 관계일 때만 조회 가능. 오래된 순으로 반환한다.",
    responses={403: {"description": "L1 이상 매칭 관계가 없음"}},
)
async def list_messages(session: Session, user: CurrentUser, partner_id: int) -> list[MessageResponse]:
    messages = await ChatService(session).list_messages(user, partner_id)
    return [MessageResponse.model_validate(m) for m in messages]
