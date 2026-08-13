from sqlalchemy.ext.asyncio import AsyncSession

from app.models.point_account import SEED_POINTS, PointAccount


class PointAccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int) -> PointAccount:
        account = await self.session.get(PointAccount, user_id)
        if account is None:
            account = PointAccount(user_id=user_id, balance=SEED_POINTS)
            self.session.add(account)
            await self.session.commit()
            await self.session.refresh(account)
        return account
