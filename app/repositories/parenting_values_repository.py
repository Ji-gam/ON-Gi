from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.baumrind_questions import ParentingTypeLabel
from app.models.parenting_values import ParentingValuesHistory, ParentingValuesProfile, ParentingValuesSource


class ParentingValuesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> ParentingValuesProfile | None:
        return await self.session.get(ParentingValuesProfile, user_id)

    def add_history(
        self,
        user_id: int,
        *,
        warmth_score: float,
        control_score: float,
        type_label: ParentingTypeLabel,
        source: ParentingValuesSource,
    ) -> None:
        self.session.add(
            ParentingValuesHistory(
                user_id=user_id,
                warmth_score=warmth_score,
                control_score=control_score,
                type_label=type_label,
                source=source,
            )
        )
