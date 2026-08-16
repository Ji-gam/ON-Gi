"""MAT 도메인 - 매칭 후보(REQ-F-MAT-01/02/03/05/12)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies import get_current_user
from app.dtos.matching_dto import CandidateResponse
from app.services.matching_service import MatchingService
from auth_kit.models import User

mat_router = APIRouter(prefix="/mat", tags=["mat"])

Session = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@mat_router.get(
    "/candidates",
    response_model=list[CandidateResponse],
    summary="매칭 후보 목록(하드필터+종합점수 정렬)",
    description=(
        "REQ-F-MAT-01/02/03/05/12. 거리 1km·완화불가 태그 하드필터를 통과한 후보를 "
        "가치관유사도 35%+상보스코어 35%+거리·개월수유사도·신뢰점수 각 10%로 정렬한다."
    ),
    responses={400: {"description": "본인 보호자 프로필 미등록"}},
)
async def list_candidates(session: Session, user: CurrentUser, for_date: date | None = None) -> list[CandidateResponse]:
    candidates = await MatchingService(session).find_candidates(user, for_date or date.today())
    return [
        CandidateResponse(
            user_id=c.user_id,
            nickname=c.nickname,
            total_score=c.total_score,
            values_similarity=c.values_similarity,
            complementary_score=c.complementary_score,
            distance_m=c.distance_m,
            age_similarity=c.age_similarity,
            trust_score=c.trust_score,
            average_rating=c.average_rating,
            top_tags=c.top_tags,
            reason=c.reason,
        )
        for c in candidates
    ]
