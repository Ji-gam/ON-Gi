from datetime import datetime

from pydantic import BaseModel, Field


class BalanceResponse(BaseModel):
    user_id: int
    balance: int
    held_balance: int = Field(default=0, description="REQ-F-PNT-05 홀드 중인 포인트")


class TransactionEntryResponse(BaseModel):
    counterparty_id: int
    reason: str
    amount: int
    created_at: datetime
