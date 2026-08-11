from datetime import datetime

from pydantic import BaseModel


class BalanceResponse(BaseModel):
    user_id: int
    balance: int


class TransactionEntryResponse(BaseModel):
    counterparty_id: int
    reason: str
    amount: int
    created_at: datetime
