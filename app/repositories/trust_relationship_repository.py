from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trust_level import TrustLevelHistory, TrustRelationship


def _normalize_pair(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    return (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)


class TrustRelationshipRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_a_id: int, user_b_id: int) -> TrustRelationship | None:
        low, high = _normalize_pair(user_a_id, user_b_id)
        result = await self.session.execute(
            select(TrustRelationship).where(TrustRelationship.user_a_id == low, TrustRelationship.user_b_id == high)
        )
        return result.scalar_one_or_none()

    def add(self, relationship: TrustRelationship) -> None:
        self.session.add(relationship)

    def add_history(self, history: TrustLevelHistory) -> None:
        self.session.add(history)
