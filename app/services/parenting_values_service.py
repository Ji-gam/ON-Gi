from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.baumrind_questions import BAUMRIND_QUESTIONS, ParentingDimension, classify_type
from app.models.parenting_values import ParentingValuesProfile, ParentingValuesSource
from app.repositories.parenting_values_repository import ParentingValuesRepository
from auth_kit.models import User


class ParentingValuesService:
    """REQ-F-ACC-07/08/10. 진단은 1인당 1건 - 재진단은 upsert하고 이력에 스냅샷을 남긴다."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ParentingValuesRepository(session)

    def _score_answers(self, answers: list[int]) -> tuple[float, float]:
        if len(answers) != len(BAUMRIND_QUESTIONS):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"응답은 {len(BAUMRIND_QUESTIONS)}개여야 합니다.")
        for answer in answers:
            if not 1 <= answer <= 5:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "응답은 1~5점이어야 합니다.")

        paired = list(zip(answers, BAUMRIND_QUESTIONS, strict=True))
        warmth = [a for a, q in paired if q.dimension == ParentingDimension.WARMTH]
        control = [a for a, q in paired if q.dimension == ParentingDimension.CONTROL]
        return sum(warmth) / len(warmth), sum(control) / len(control)

    async def submit_questionnaire(self, user: User, answers: list[int]) -> ParentingValuesProfile:
        warmth_score, control_score = self._score_answers(answers)
        type_label = classify_type(warmth_score, control_score)

        profile = await self.repo.get(user.id)
        if profile is None:
            profile = ParentingValuesProfile(user_id=user.id)
            self.session.add(profile)

        profile.warmth_score = warmth_score
        profile.control_score = control_score
        profile.type_label = type_label

        self.repo.add_history(
            user.id,
            warmth_score=warmth_score,
            control_score=control_score,
            type_label=type_label,
            source=ParentingValuesSource.QUESTIONNAIRE,
        )
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def submit_narrative(self, user: User, narrative: str) -> ParentingValuesProfile:
        """REQ-F-ACC-10. LLM 보정은 스텁 - `docs/tasks/T-ACC-3.md` 가정 참고. ai_worker 게이트웨이가
        준비되면 여기서 실제 벡터 보정을 호출하도록 교체한다. 지금은 서술만 저장하고 현재 점수를 그대로
        이력에 재기록한다."""
        profile = await self.repo.get(user.id)
        if profile is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "자유 서술 전에 8문항 진단을 먼저 완료해주세요.")

        profile.narrative = narrative
        self.repo.add_history(
            user.id,
            warmth_score=profile.warmth_score,
            control_score=profile.control_score,
            type_label=profile.type_label,
            source=ParentingValuesSource.NARRATIVE,
        )
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def get_profile(self, user: User) -> ParentingValuesProfile:
        profile = await self.repo.get(user.id)
        if profile is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "등록된 양육 가치관 진단이 없습니다.")
        return profile
