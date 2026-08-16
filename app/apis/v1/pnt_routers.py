"""PNT 도메인 - 포인트 복식부기 원장 + 돌봄 정산(REQ-F-PNT-01/02/03/04)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies import get_current_user
from app.dtos.point_dto import BalanceResponse, TransactionEntryResponse
from app.services.point_ledger_service import PointLedgerService
from auth_kit.models import User

pnt_router = APIRouter(prefix="/pnt", tags=["pnt"])

Session = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@pnt_router.get(
    "/balance",
    response_model=BalanceResponse,
    summary="포인트 잔액 조회",
    description="REQ-F-PNT-03/04. 최초 조회 시 시드 포인트로 계정이 생성된다.",
)
async def get_balance(session: Session, user: CurrentUser) -> BalanceResponse:
    service = PointLedgerService(session)
    balance = await service.get_balance(user.id)
    held_balance = await service.get_held_balance(user.id)
    return BalanceResponse(user_id=user.id, balance=balance, held_balance=held_balance)


@pnt_router.get(
    "/transactions",
    response_model=list[TransactionEntryResponse],
    summary="포인트 거래 내역 조회",
    description="REQ-F-PNT-03. 최신순으로 상대·사유·증감을 반환한다.",
)
async def list_transactions(session: Session, user: CurrentUser) -> list[TransactionEntryResponse]:
    entries = await PointLedgerService(session).list_transactions(user.id)
    return [
        TransactionEntryResponse(
            counterparty_id=entry.counterparty_id,
            reason=transaction.reason,
            amount=entry.amount,
            created_at=transaction.created_at,
        )
        for entry, transaction in entries
    ]
