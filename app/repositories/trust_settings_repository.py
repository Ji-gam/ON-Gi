from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trust_settings import TrustSettings


class TrustSettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int) -> TrustSettings:
        settings = await self.session.get(TrustSettings, user_id)
        if settings is None:
            settings = TrustSettings(user_id=user_id)
            self.session.add(settings)
            await self.session.commit()
            await self.session.refresh(settings)
        return settings
