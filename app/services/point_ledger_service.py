"""REQ-F-PNT-01/02/03/04. 복식부기 원장 - 거래 1건은 항상 대칭된 두 entry(+amount/-amount)로
기록해 합계 0을 구조적으로 보장한다. 돌봄 정산은 `actual_minutes // 30`(슬롯) 단위로 요청자
차감·제공자 적립을 한 거래로 기록한다.
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_session import CareSession
from app.models.point_account import NEGATIVE_BALANCE_LIMIT
from app.models.point_ledger import PointEntry, PointTransaction
from app.repositories.point_account_repository import PointAccountRepository
from app.repositories.point_ledger_repository import PointLedgerRepository

SLOT_MINUTES = 30
SETTLEMENT_REASON = "돌봄 정산"
CARE_SESSION_REFERENCE_TYPE = "care_session"
BALANCE_LIMIT_MESSAGE = "포인트 잔액 한도를 초과해 새 요청을 생성할 수 없습니다."


class PointLedgerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = PointAccountRepository(session)
        self.ledger_repo = PointLedgerRepository(session)

    async def get_balance(self, user_id: int) -> int:
        account = await self.account_repo.get_or_create(user_id)
        return account.balance

    async def list_transactions(self, user_id: int) -> list[tuple[PointEntry, PointTransaction]]:
        await self.account_repo.get_or_create(user_id)
        return await self.ledger_repo.list_entries_for_user(user_id)

    async def ensure_can_request(self, requester_id: int) -> None:
        account = await self.account_repo.get_or_create(requester_id)
        if account.balance <= NEGATIVE_BALANCE_LIMIT:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, BALANCE_LIMIT_MESSAGE)

    async def _transfer(
        self,
        *,
        payer_id: int,
        payee_id: int,
        amount: int,
        reason: str,
        reference_type: str | None = None,
        reference_id: int | None = None,
    ) -> PointTransaction:
        payer_account = await self.account_repo.get_or_create(payer_id)
        payee_account = await self.account_repo.get_or_create(payee_id)

        transaction = PointTransaction(reason=reason, reference_type=reference_type, reference_id=reference_id)
        self.ledger_repo.add_transaction(transaction)
        await self.session.flush()

        self.ledger_repo.add_entry(
            PointEntry(transaction_id=transaction.id, user_id=payer_id, counterparty_id=payee_id, amount=-amount)
        )
        self.ledger_repo.add_entry(
            PointEntry(transaction_id=transaction.id, user_id=payee_id, counterparty_id=payer_id, amount=amount)
        )
        payer_account.balance -= amount
        payee_account.balance += amount

        await self.session.commit()
        await self.session.refresh(transaction)
        return transaction

    async def settle_care_session(self, care_session: CareSession) -> PointTransaction | None:
        if await self.ledger_repo.has_settled(CARE_SESSION_REFERENCE_TYPE, care_session.id):
            return None

        slots = (care_session.actual_minutes or 0) // SLOT_MINUTES
        if slots <= 0:
            return None

        return await self._transfer(
            payer_id=care_session.requester_id,
            payee_id=care_session.provider_id,
            amount=slots,
            reason=SETTLEMENT_REASON,
            reference_type=CARE_SESSION_REFERENCE_TYPE,
            reference_id=care_session.id,
        )
