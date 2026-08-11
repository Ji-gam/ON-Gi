"""CAR 도메인 - 돌봄 요청 생성·수락·거절(REQ-F-CAR-01/02) + 체크인/체크아웃/일지(REQ-F-CAR-03/05/06)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies import get_current_user
from app.dtos.care_log_dto import CareLogResponse, CareLogUpsert
from app.dtos.care_session_dto import CareRequestCreate, CareSessionResponse, CheckinRequest
from app.services.care_log_service import CareLogService
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
    responses={400: {"description": "상보 가능 시간대가 아니거나 구간·아동 지정이 올바르지 않음"}},
)
async def create_request(session: Session, user: CurrentUser, request: CareRequestCreate) -> CareSessionResponse:
    care_session = await CareSessionService(session).create_request(
        user,
        request.provider_id,
        request.child_id,
        request.meeting_h3,
        request.care_date,
        request.start_slot,
        request.end_slot,
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


@car_router.post(
    "/requests/{session_id}/checkin",
    response_model=CareSessionResponse,
    summary="돌봄 체크인(GPS)",
    description="REQ-F-CAR-03. 약속 장소 반경(200m) 밖 체크인은 사유 입력이 필요하다.",
    responses={400: {"description": "반경 밖 체크인 사유 누락"}, 409: {"description": "확정 아님/중복 체크인"}},
)
async def checkin(session: Session, user: CurrentUser, session_id: int, request: CheckinRequest) -> CareSessionResponse:
    care_session = await CareSessionService(session).checkin(session_id, user, request.lat, request.lng, request.reason)
    return CareSessionResponse.model_validate(care_session)


@car_router.post(
    "/requests/{session_id}/checkout",
    response_model=CareSessionResponse,
    summary="돌봄 체크아웃",
    description="REQ-F-CAR-05. 체크인 이후에만 가능. 실제 돌봄 시간(분)이 포인트 정산 근거로 확정된다.",
    responses={409: {"description": "체크인 전이거나 이미 체크아웃함"}},
)
async def checkout(session: Session, user: CurrentUser, session_id: int) -> CareSessionResponse:
    care_session = await CareSessionService(session).checkout(session_id, user)
    return CareSessionResponse.model_validate(care_session)


@car_router.put(
    "/requests/{session_id}/journal",
    response_model=CareLogResponse,
    summary="돌봄 일지 작성(upsert)",
    description="REQ-F-CAR-06. 제공자만 작성 가능. 알레르기 등록 아동은 관련 항목 미입력 시 저장이 거부된다.",
    responses={
        400: {"description": "알레르기 항목 누락"},
        404: {"description": "세션 없음"},
        409: {"description": "확정 아님"},
    },
)
async def upsert_journal(
    session: Session, user: CurrentUser, session_id: int, request: CareLogUpsert
) -> CareLogResponse:
    care_log = await CareLogService(session).upsert(
        session_id,
        user,
        meal=request.meal,
        sleep=request.sleep,
        mood=request.mood,
        note=request.note,
        allergy_note=request.allergy_note,
    )
    return CareLogResponse.model_validate(care_log)


@car_router.get(
    "/requests/{session_id}/journal",
    response_model=CareLogResponse | None,
    summary="돌봄 일지 조회",
    description="REQ-F-CAR-06. 요청자/제공자 모두 조회 가능.",
    responses={404: {"description": "세션 없음"}},
)
async def get_journal(session: Session, user: CurrentUser, session_id: int) -> CareLogResponse | None:
    care_log = await CareLogService(session).get(session_id, user)
    return CareLogResponse.model_validate(care_log) if care_log else None
