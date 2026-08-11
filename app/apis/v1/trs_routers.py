"""TRS 도메인 - 상호 평가 + 신뢰 점수(REQ-F-TRS-05/06/07/08)."""

from typing import Annotated

from fastapi import APIRouter, Depends
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
from app.services.trust_evaluation_service import TrustEvaluationService
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
