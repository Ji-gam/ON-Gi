"""REQ-F-COM-01. L1 이상 관계(TrustRelationship 존재)에서만 1:1 채팅을 허용한다."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.pii_mask import mask_pii
from app.models.chat_message import ChatMessage
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.trust_relationship_repository import TrustRelationshipRepository
from auth_kit.models import User

NOT_MATCHED_MESSAGE = "매칭 관계(L1 이상)가 있어야 채팅할 수 있습니다."


class ChatService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.relationship_repo = TrustRelationshipRepository(session)
        self.message_repo = ChatMessageRepository(session)

    async def _require_relationship_id(self, user_id: int, partner_id: int) -> int:
        relationship = await self.relationship_repo.get(user_id, partner_id)
        if relationship is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_MATCHED_MESSAGE)
        return relationship.id

    async def send_message(self, sender: User, partner_id: int, content: str) -> ChatMessage:
        relationship_id = await self._require_relationship_id(sender.id, partner_id)
        masked_content, pii_masked = mask_pii(content)
        message = ChatMessage(
            relationship_id=relationship_id, sender_id=sender.id, content=masked_content, pii_masked=pii_masked
        )
        self.message_repo.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def list_messages(self, user: User, partner_id: int) -> list[ChatMessage]:
        relationship_id = await self._require_relationship_id(user.id, partner_id)
        return await self.message_repo.list_for_relationship(relationship_id)
