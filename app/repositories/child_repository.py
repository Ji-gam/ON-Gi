from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.children import Child


class ChildRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_user(self, user_id: int) -> list[Child]:
        rows = await self.session.scalars(select(Child).where(Child.user_id == user_id).order_by(Child.id))
        return list(rows.all())

    async def get(self, child_id: int) -> Child | None:
        return await self.session.get(Child, child_id)

    def add(self, child: Child) -> None:
        self.session.add(child)

    async def delete(self, child: Child) -> None:
        await self.session.delete(child)
