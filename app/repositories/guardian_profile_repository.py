from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.guardian_profile import GuardianProfile, GuardianTag


class GuardianProfileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> GuardianProfile | None:
        return await self.session.get(GuardianProfile, user_id)

    async def list_tags(self, user_id: int) -> list[str]:
        rows = await self.session.scalars(select(GuardianTag.tag_code).where(GuardianTag.user_id == user_id))
        return sorted(rows.all())

    async def replace_tags(self, user_id: int, tag_codes: list[str]) -> None:
        await self.session.execute(delete(GuardianTag).where(GuardianTag.user_id == user_id))
        for code in tag_codes:
            self.session.add(GuardianTag(user_id=user_id, tag_code=code))
