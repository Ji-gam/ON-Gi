"""ADM 도메인 - 핵심 지표 집계(REQ-F-ADM-02) + 아동 안전 긴급 정지(REQ-F-ADM-05)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies import get_current_user
from app.dtos.adm_dto import CoreMetricsResponse, SuspendedSessionResponse, SuspendRequest
from app.services.admin_service import AdminMetricsService, AdminSuspendService
from auth_kit.models import User

adm_router = APIRouter(prefix="/adm", tags=["adm"])

Session = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@adm_router.get(
    "/metrics",
    response_model=CoreMetricsResponse,
    summary="핵심 지표 3종 조회",
    description="REQ-F-ADM-02. 상보 후보 보유율/L2→L3 전이율/재매칭률을 `hypothesis_events` 로그로부터 집계한다.",
)
async def get_core_metrics(session: Session, user: CurrentUser) -> CoreMetricsResponse:
    metrics = await AdminMetricsService(session).get_core_metrics()
    return CoreMetricsResponse(**metrics)


@adm_router.post(
    "/users/{user_id}/suspend",
    response_model=list[SuspendedSessionResponse],
    summary="아동 안전 긴급 정지",
    description="REQ-F-ADM-05. 운영자 전용. 대상 계정을 즉시 제재하고 진행/예정 세션을 중단·취소하며 "
    "상대에게 알림을 발송한다.",
    responses={403: {"description": "운영자가 아님"}, 404: {"description": "대상 계정 없음"}},
)
async def suspend_user(
    session: Session, user: CurrentUser, user_id: int, request: SuspendRequest
) -> list[SuspendedSessionResponse]:
    stopped_sessions = await AdminSuspendService(session).emergency_suspend(user, user_id, request.reason)
    return [
        SuspendedSessionResponse(
            session_id=cs.id,
            counterparty_id=cs.provider_id if user_id == cs.requester_id else cs.requester_id,
        )
        for cs in stopped_sessions
    ]
