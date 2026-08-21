from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageSendRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: int
    content: str
    pii_masked: bool = Field(description="REQ-F-COM-01. 연락처 패턴이 감지돼 마스킹됐는지 여부(경고 노출용)")
    created_at: datetime
