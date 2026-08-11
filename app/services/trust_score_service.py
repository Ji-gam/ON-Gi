"""REQ-F-TRS-06/08. 신뢰 점수 = w1×별점정규화 + w2×이행확인응답률 + w3×(1-노쇼율) + w4×일지작성률.
이행확인응답률(REQ-F-TRS-02)·노쇼율(REQ-F-CAR-07)은 아직 구현되지 않은 도메인이라 스텁값을
사용한다(docs/tasks/T-TRS-1.md 가정 참고).
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_log import CareLog
from app.models.care_session import CareSession
from app.models.trust_weights import TrustWeightHistory, TrustWeights
from app.repositories.care_evaluation_repository import CareEvaluationRepository
from app.repositories.trust_weight_repository import TrustWeightRepository
from auth_kit.models import User

RESPONSE_RATE_STUB = 1.0  # TODO(T-TRS-1→T-TRS-2): REQ-F-TRS-02 이행확인 응답률 연동 전까지 스텁
NO_SHOW_RATE_STUB = 0.0  # TODO(T-TRS-1→후속 노쇼 Task): REQ-F-CAR-07 노쇼 이력 연동 전까지 스텁
NEUTRAL_RATING = 0.5  # 평가 없는 신규 사용자에게 페널티를 주지 않기 위한 중립값(별점 3점 상당)


class TrustScoreService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.evaluation_repo = CareEvaluationRepository(session)
        self.weight_repo = TrustWeightRepository(session)

    async def get_weights(self) -> TrustWeights:
        return await self.weight_repo.get_or_create()

    async def update_weights(self, admin: User, w1: float, w2: float, w3: float, w4: float) -> TrustWeights:
        if not admin.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "운영자만 가중치를 변경할 수 있습니다.")
        if abs((w1 + w2 + w3 + w4) - 1.0) > 1e-6:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "가중치 합은 1.0이어야 합니다.")

        weights = await self.weight_repo.get_or_create()
        self.weight_repo.add_history(
            TrustWeightHistory(
                changed_by_user_id=admin.id,
                previous_w1=weights.w1,
                previous_w2=weights.w2,
                previous_w3=weights.w3,
                previous_w4=weights.w4,
            )
        )
        weights.w1, weights.w2, weights.w3, weights.w4 = w1, w2, w3, w4
        await self.session.commit()
        await self.session.refresh(weights)
        return weights

    async def _journal_completion_rate(self, provider_id: int) -> float:
        completed = await self.session.execute(
            select(CareSession.id).where(CareSession.provider_id == provider_id, CareSession.checkout_at.is_not(None))
        )
        completed_ids = list(completed.scalars().all())
        if not completed_ids:
            return 1.0  # 완료된 세션이 없는 신규 제공자 - 이력 부재를 페널티로 취급하지 않음

        logged = await self.session.execute(
            select(func.count(CareLog.session_id)).where(CareLog.session_id.in_(completed_ids))
        )
        return (logged.scalar() or 0) / len(completed_ids)

    async def calculate_score(self, user_id: int) -> float:
        ratings = await self.evaluation_repo.list_ratings_for_evaluatee(user_id)
        rating_norm = (sum(ratings) / len(ratings) - 1) / 4 if ratings else NEUTRAL_RATING

        journal_rate = await self._journal_completion_rate(user_id)
        weights = await self.get_weights()

        return (
            weights.w1 * rating_norm
            + weights.w2 * RESPONSE_RATE_STUB
            + weights.w3 * (1 - NO_SHOW_RATE_STUB)
            + weights.w4 * journal_rate
        )
