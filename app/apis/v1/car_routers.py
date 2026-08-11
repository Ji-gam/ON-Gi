"""CAR 도메인 - 돌봄 요청 생성·수락·거절(REQ-F-CAR-01/02)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies import get_current_user
from app.dtos.care_session_dto import CareRequestCreate, CareSessionResponse
from app.services.care_session_service import CareSessionService
from auth_kit.models import User

car_router = APIRouter(prefix="/car", tags=["car"])

Session = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@car_router.post(
    "/requests",
    response_model=CareSessionResponse,
    summary="돌봄 요청 생성",
    description="REQ-F-CAR-01. 제공자가 상보 가능한(제공자 가용+요청자 불가) 구간만 요청할 수 있다.",
    responses={400: {"description": "상보 가능 시간대가 아니거나 구간이 올바르지 않음"}},
)
async def create_request(session: Session, user: CurrentUser, request: CareRequestCreate) -> CareSessionResponse:
    care_session = await CareSessionService(session).create_request(
        user, request.provider_id, request.care_date, request.start_slot, request.end_slot
    )
    return CareSessionResponse.model_validate(care_session)


@car_router.post(
    "/requests/{session_id}/accept",
    response_model=CareSessionResponse,
    summary="돌봄 요청 수락",
    description="REQ-F-CAR-02. 제공자 본인만 수락 가능. 세션 상태가 CONFIRMED로 전이된다.",
    responses={404: {"description": "요청 없음"}, 409: {"description": "이미 처리된 요청"}},
)
async def accept_request(session: Session, user: CurrentUser, session_id: int) -> CareSessionResponse:
    care_session = await CareSessionService(session).accept(session_id, user)
    return CareSessionResponse.model_validate(care_session)


@car_router.post(
    "/requests/{session_id}/reject",
    response_model=CareSessionResponse,
    summary="돌봄 요청 거절",
    description="REQ-F-CAR-02. 제공자 본인만 거절 가능. 세션 상태가 REJECTED로 전이된다.",
    responses={404: {"description": "요청 없음"}, 409: {"description": "이미 처리된 요청"}},
)
async def reject_request(session: Session, user: CurrentUser, session_id: int) -> CareSessionResponse:
    care_session = await CareSessionService(session).reject(session_id, user)
    return CareSessionResponse.model_validate(care_session)
