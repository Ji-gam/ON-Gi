from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trust_weights import TrustWeightHistory, TrustWeights

_SINGLETON_ID = 1
DEFAULT_WEIGHTS = (0.4, 0.2, 0.2, 0.2)  # REQ-F-TRS-08 초기값 미명시 - 가정(docs/tasks/T-TRS-1.md)


class TrustWeightRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self) -> TrustWeights:
        weights = await self.session.get(TrustWeights, _SINGLETON_ID)
        if weights is None:
            w1, w2, w3, w4 = DEFAULT_WEIGHTS
            weights = TrustWeights(id=_SINGLETON_ID, w1=w1, w2=w2, w3=w3, w4=w4)
            self.session.add(weights)
            await self.session.commit()
            await self.session.refresh(weights)
        return weights

    def add_history(self, history: TrustWeightHistory) -> None:
        self.session.add(history)
