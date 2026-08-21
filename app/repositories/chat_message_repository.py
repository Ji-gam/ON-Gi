from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage


class ChatMessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, message: ChatMessage) -> None:
        self.session.add(message)

    async def list_for_relationship(self, relationship_id: int) -> list[ChatMessage]:
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.relationship_id == relationship_id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
        return list(result.scalars().all())
