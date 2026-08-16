from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hypothesis_event import HypothesisEvent, HypothesisEventType


class HypothesisEventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, event: HypothesisEvent) -> None:
        self.session.add(event)

    async def list_by_type(self, event_type: HypothesisEventType) -> list[HypothesisEvent]:
        result = await self.session.execute(select(HypothesisEvent).where(HypothesisEvent.event_type == event_type))
        return list(result.scalars().all())
