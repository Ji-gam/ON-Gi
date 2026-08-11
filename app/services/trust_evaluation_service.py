"""REQ-F-TRS-05. 돌봄 종료(체크아웃) 후 세션 참여자 본인만, 세션당 1회 평가를 제출할 수 있다."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_evaluation import CareEvaluation, CareEvaluationTag
from app.repositories.care_evaluation_repository import CareEvaluationRepository
from app.repositories.care_session_repository import CareSessionRepository
from auth_kit.models import User


class TrustEvaluationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.evaluation_repo = CareEvaluationRepository(session)
        self.session_repo = CareSessionRepository(session)

    async def submit(self, session_id: int, evaluator: User, rating: int, tags: list[str]) -> CareEvaluation:
        if not (1 <= rating <= 5):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "별점은 1~5 사이여야 합니다.")

        care_session = await self.session_repo.get(session_id)
        if care_session is None or evaluator.id not in (care_session.requester_id, care_session.provider_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
        if care_session.checkout_at is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "종료되지 않은 세션입니다.")

        existing = await self.evaluation_repo.get_by_session_and_evaluator(session_id, evaluator.id)
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 평가를 제출했습니다.")

        evaluatee_id = (
            care_session.provider_id if evaluator.id == care_session.requester_id else care_session.requester_id
        )
        evaluation = CareEvaluation(
            session_id=session_id, evaluator_id=evaluator.id, evaluatee_id=evaluatee_id, rating=rating
        )
        self.evaluation_repo.add(evaluation)
        await self.session.flush()
        for tag_code in tags:
            self.evaluation_repo.add_tag(CareEvaluationTag(evaluation_id=evaluation.id, tag_code=tag_code))

        await self.session.commit()
        await self.session.refresh(evaluation)
        return evaluation
