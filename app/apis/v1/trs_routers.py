"""TRS 도메인 - 상호 평가 + 신뢰 점수(REQ-F-TRS-05/06/07/08) + 신뢰 등급 상태머신
(REQ-F-TRS-01/02/03/04)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies import get_current_user
from app.dtos.trust_dto import (
    EvaluationResponse,
    EvaluationSubmit,
    TrustScoreResponse,
    TrustWeightsResponse,
    TrustWeightsUpdate,
)
from app.dtos.trust_level_dto import (
    DemoteRequest,
    JointCareSessionCreate,
    JointCareSessionResponse,
    RequiredJointCountUpdate,
    TrustRelationshipResponse,
    TrustSettingsResponse,
)
from app.services.trust_evaluation_service import TrustEvaluationService
from app.services.trust_level_service import TrustLevelService
from app.services.trust_score_service import TrustScoreService
from auth_kit.models import User

trs_router = APIRouter(prefix="/trs", tags=["trs"])

Session = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@trs_router.post(
    "/sessions/{session_id}/evaluations",
    response_model=EvaluationResponse,
    summary="돌봄 상호 평가 제출",
    description="REQ-F-TRS-05. 체크아웃 완료된 세션의 참여자만, 세션당 1회 제출할 수 있다.",
    responses={404: {"description": "세션 없음"}, 409: {"description": "미종료/중복 제출"}},
)
async def submit_evaluation(
    session: Session, user: CurrentUser, session_id: int, request: EvaluationSubmit
) -> EvaluationResponse:
    evaluation = await TrustEvaluationService(session).submit(session_id, user, request.rating, request.tags)
    return EvaluationResponse.model_validate(evaluation)


@trs_router.get(
    "/users/{user_id}/score",
    response_model=TrustScoreResponse,
    summary="신뢰 점수 조회",
    description="REQ-F-TRS-06/08. 가중합 신뢰 점수를 조회한다.",
)
async def get_score(session: Session, user: CurrentUser, user_id: int) -> TrustScoreResponse:
    score = await TrustScoreService(session).calculate_score(user_id)
    return TrustScoreResponse(user_id=user_id, score=score)


@trs_router.get(
    "/weights",
    response_model=TrustWeightsResponse,
    summary="신뢰 점수 가중치 조회",
    description="REQ-F-TRS-08.",
)
async def get_weights(session: Session, user: CurrentUser) -> TrustWeightsResponse:
    weights = await TrustScoreService(session).get_weights()
    return TrustWeightsResponse.model_validate(weights)


@trs_router.put(
    "/weights",
    response_model=TrustWeightsResponse,
    summary="신뢰 점수 가중치 변경(운영자)",
    description="REQ-F-TRS-08. 운영자만 변경 가능, 가중치 합은 1.0이어야 하며 변경 시 이력이 남는다.",
    responses={400: {"description": "가중치 합이 1.0이 아님"}, 403: {"description": "운영자 아님"}},
)
async def update_weights(session: Session, user: CurrentUser, request: TrustWeightsUpdate) -> TrustWeightsResponse:
    weights = await TrustScoreService(session).update_weights(user, request.w1, request.w2, request.w3, request.w4)
    return TrustWeightsResponse.model_validate(weights)


@trs_router.get(
    "/relationships/{other_user_id}",
    response_model=TrustRelationshipResponse | None,
    summary="상대와의 신뢰 등급 조회",
    description="REQ-F-TRS-01. 관계가 아직 없으면(매칭 요청/수락 전) null을 반환한다.",
)
async def get_relationship(session: Session, user: CurrentUser, other_user_id: int) -> TrustRelationshipResponse | None:
    relationship = await TrustLevelService(session).get_relationship(user.id, other_user_id)
    return TrustRelationshipResponse.model_validate(relationship) if relationship else None


@trs_router.post(
    "/relationships/{other_user_id}/joint-sessions",
    response_model=JointCareSessionResponse,
    summary="공동육아 일정 등록",
    description="REQ-F-TRS-02. 매칭 관계(L1 이상)가 있어야 등록할 수 있으며, 최초 등록 시 L2로 전이한다.",
    responses={404: {"description": "매칭 관계 없음"}},
)
async def create_joint_session(
    session: Session, user: CurrentUser, other_user_id: int, request: JointCareSessionCreate
) -> JointCareSessionResponse:
    if other_user_id != request.partner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "경로의 상대와 요청 본문의 상대가 일치하지 않습니다.")
    joint_session = await TrustLevelService(session).schedule_joint_session(
        user, request.partner_id, request.place, request.scheduled_date
    )
    return JointCareSessionResponse.model_validate(joint_session)


@trs_router.post(
    "/joint-sessions/{joint_session_id}/confirm",
    response_model=JointCareSessionResponse,
    summary="공동육아 완료 확인",
    description="REQ-F-TRS-02. 양측이 모두 확인하면 1회로 집계되고, 필요 횟수 충족 시 L3로 전이한다.",
    responses={403: {"description": "일정 당사자 아님"}, 404: {"description": "일정 없음"}},
)
async def confirm_joint_session(session: Session, user: CurrentUser, joint_session_id: int) -> JointCareSessionResponse:
    joint_session = await TrustLevelService(session).confirm_joint_session(joint_session_id, user)
    return JointCareSessionResponse.model_validate(joint_session)


@trs_router.put(
    "/settings/joint-count",
    response_model=TrustSettingsResponse,
    summary="공동육아 필요 횟수 설정",
    description="REQ-F-TRS-03. 기본 3회, 하한선 1회.",
    responses={400: {"description": "1회 미만으로 설정 시도"}},
)
async def update_required_joint_count(
    session: Session, user: CurrentUser, request: RequiredJointCountUpdate
) -> TrustSettingsResponse:
    settings = await TrustLevelService(session).set_required_count(user, request.required_joint_count)
    return TrustSettingsResponse.model_validate(settings)


@trs_router.post(
    "/relationships/demote",
    response_model=TrustRelationshipResponse,
    summary="신뢰 등급 강등(운영자)",
    description="REQ-F-TRS-01 역방향 전이. 신고 도메인 미구현으로 운영자가 사유를 남기고 수동 강등한다.",
    responses={
        400: {"description": "이미 최저 등급"},
        403: {"description": "운영자 아님"},
        404: {"description": "관계 없음"},
    },
)
async def demote_relationship(session: Session, user: CurrentUser, request: DemoteRequest) -> TrustRelationshipResponse:
    relationship = await TrustLevelService(session).demote(user, request.user_a_id, request.user_b_id, request.reason)
    return TrustRelationshipResponse.model_validate(relationship)
