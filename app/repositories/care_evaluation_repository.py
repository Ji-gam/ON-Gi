from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_evaluation import CareEvaluation, CareEvaluationTag
from app.models.care_session import CareSession


class CareEvaluationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_session_and_evaluator(self, session_id: int, evaluator_id: int) -> CareEvaluation | None:
        result = await self.session.execute(
            select(CareEvaluation).where(
                CareEvaluation.session_id == session_id, CareEvaluation.evaluator_id == evaluator_id
            )
        )
        return result.scalar_one_or_none()

    def add(self, evaluation: CareEvaluation) -> None:
        self.session.add(evaluation)

    def add_tag(self, tag: CareEvaluationTag) -> None:
        self.session.add(tag)

    async def list_ratings_for_evaluatee(self, evaluatee_id: int) -> list[int]:
        result = await self.session.execute(
            select(CareEvaluation.rating).where(CareEvaluation.evaluatee_id == evaluatee_id)
        )
        return list(result.scalars().all())

    async def top_tags_for_evaluatee(self, evaluatee_id: int, limit: int = 3) -> list[str]:
        result = await self.session.execute(
            select(CareEvaluationTag.tag_code, func.count(CareEvaluationTag.id).label("cnt"))
            .join(CareEvaluation, CareEvaluation.id == CareEvaluationTag.evaluation_id)
            .where(CareEvaluation.evaluatee_id == evaluatee_id)
            .group_by(CareEvaluationTag.tag_code)
            .order_by(func.count(CareEvaluationTag.id).desc())
            .limit(limit)
        )
        return [row[0] for row in result.all()]

    async def has_pending_evaluation(self, user_id: int) -> bool:
        """체크아웃 완료됐지만 user_id가 평가자로 아직 제출하지 않은 세션이 있는지."""
        completed = await self.session.execute(
            select(CareSession.id).where(
                CareSession.checkout_at.is_not(None),
                (CareSession.requester_id == user_id) | (CareSession.provider_id == user_id),
            )
        )
        completed_ids = set(completed.scalars().all())
        if not completed_ids:
            return False

        submitted = await self.session.execute(
            select(CareEvaluation.session_id).where(
                CareEvaluation.evaluator_id == user_id, CareEvaluation.session_id.in_(completed_ids)
            )
        )
        submitted_ids = set(submitted.scalars().all())
        return bool(completed_ids - submitted_ids)
