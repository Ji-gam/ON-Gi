"""REQ-F-PNT-01/02/03/04/05. 복식부기 원장 - 거래 1건은 항상 대칭된 두 entry(+amount/-amount)로
기록해 합계 0을 구조적으로 보장한다. 돌봄 정산은 `actual_minutes // 30`(슬롯) 단위로 요청자
차감·제공자 적립을 한 거래로 기록한다.

REQ-F-PNT-05 홀드(예치)는 요청자 본인 계정 안에서만 `balance`→`held_balance`로 자리를 옮길 뿐
상대에게 이전되지 않으므로 PointTransaction/PointEntry를 만들지 않는다(두 당사자 간 실제 이동이
아니라 예약이기 때문). 완료 시 정산되는 슬롯만큼만 실제 이동으로 기록하고 미사용분은 반환한다.
취소 마감(`CANCELLATION_DEADLINE_HOURS`) 이후 취소·노쇼는 홀드 전액을 상대에게 이전한다(요구사항
원문의 "일부"에 대한 구체적 비율이 없어 MVP 가정으로 전액 이전 — docs/tasks/T-PNT-2.md 참고).
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_session import CareSession
from app.models.point_account import NEGATIVE_BALANCE_LIMIT
from app.models.point_hold import PointHold, PointHoldStatus
from app.models.point_ledger import PointEntry, PointTransaction
from app.repositories.point_account_repository import PointAccountRepository
from app.repositories.point_hold_repository import PointHoldRepository
from app.repositories.point_ledger_repository import PointLedgerRepository

SLOT_MINUTES = 30
SETTLEMENT_REASON = "돌봄 정산"
CANCEL_PENALTY_REASON = "취소 페널티"
NO_SHOW_PENALTY_REASON = "노쇼 페널티"
CARE_SESSION_REFERENCE_TYPE = "care_session"
BALANCE_LIMIT_MESSAGE = "포인트 잔액 한도를 초과해 새 요청을 생성할 수 없습니다."


class PointLedgerService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = PointAccountRepository(session)
        self.ledger_repo = PointLedgerRepository(session)
        self.hold_repo = PointHoldRepository(session)

    async def get_balance(self, user_id: int) -> int:
        account = await self.account_repo.get_or_create(user_id)
        return account.balance

    async def get_held_balance(self, user_id: int) -> int:
        account = await self.account_repo.get_or_create(user_id)
        return account.held_balance

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

    async def create_hold(self, care_session: CareSession) -> PointHold:
        """REQ-F-PNT-05. 요청 확정(CONFIRMED) 시 예상 돌봄 시간(슬롯 수)만큼 요청자 계정 내에서
        `balance`→`held_balance`로 예약한다. 상대 계정은 건드리지 않으므로 원장 거래는 생성하지
        않는다."""
        amount = care_session.end_slot - care_session.start_slot
        await self.ensure_can_request(care_session.requester_id)

        payer_account = await self.account_repo.get_or_create(care_session.requester_id)
        await self.account_repo.get_or_create(care_session.provider_id)

        hold = PointHold(
            care_session_id=care_session.id,
            payer_id=care_session.requester_id,
            payee_id=care_session.provider_id,
            amount=amount,
            status=PointHoldStatus.HELD,
        )
        self.hold_repo.add(hold)
        payer_account.balance -= amount
        payer_account.held_balance += amount

        await self.session.commit()
        await self.session.refresh(hold)
        return hold

    async def _release_hold(self, hold: PointHold) -> None:
        """홀드 전액을 요청자(payer)에게 그대로 반환한다(취소 마감 전 취소, 제공자 귀책 노쇼)."""
        payer_account = await self.account_repo.get_or_create(hold.payer_id)
        payer_account.balance += hold.amount
        payer_account.held_balance -= hold.amount
        hold.status = PointHoldStatus.RELEASED

    async def _forfeit_hold(self, hold: PointHold, reason: str) -> None:
        """홀드 전액을 상대(payee)에게 이전하고 원장에 사유를 기록한다(취소 마감 이후 취소,
        요청자 귀책 노쇼)."""
        payer_account = await self.account_repo.get_or_create(hold.payer_id)
        payee_account = await self.account_repo.get_or_create(hold.payee_id)

        transaction = PointTransaction(
            reason=reason, reference_type=CARE_SESSION_REFERENCE_TYPE, reference_id=hold.care_session_id
        )
        self.ledger_repo.add_transaction(transaction)
        await self.session.flush()

        self.ledger_repo.add_entry(
            PointEntry(
                transaction_id=transaction.id, user_id=hold.payer_id, counterparty_id=hold.payee_id, amount=-hold.amount
            )
        )
        self.ledger_repo.add_entry(
            PointEntry(
                transaction_id=transaction.id, user_id=hold.payee_id, counterparty_id=hold.payer_id, amount=hold.amount
            )
        )
        payer_account.held_balance -= hold.amount
        payee_account.balance += hold.amount
        hold.status = PointHoldStatus.FORFEITED

    async def resolve_hold_on_cancel(self, care_session: CareSession, past_deadline: bool) -> None:
        """REQ-F-PNT-05. 취소 마감 시각 이전 취소는 귀책과 무관하게 홀드 전액 반환. 마감 이후
        취소는 귀책자가 요청자(홀드 보유자) 본인일 때만 상대에게 이전한다 - 제공자가 마감 이후
        취소해도 요청자에게는 잘못이 없으므로 요청자의 홀드를 몰수할 근거가 없다."""
        hold = await self.hold_repo.get_by_care_session(care_session.id)
        if hold is None or hold.status != PointHoldStatus.HELD:
            return

        if past_deadline and care_session.at_fault_user_id == hold.payer_id:
            await self._forfeit_hold(hold, CANCEL_PENALTY_REASON)
        else:
            await self._release_hold(hold)
        hold.resolved_at = care_session.cancelled_at

        await self.session.commit()

    async def resolve_hold_on_no_show(self, care_session: CareSession) -> None:
        """REQ-F-CAR-07/PNT-05. 요청자 귀책 노쇼는 홀드를 제공자에게 이전하고, 제공자 귀책
        노쇼는 요청자에게 홀드를 전액 반환한다(제공자는 애초에 홀드 대상이 아니라 페널티를
        포인트로 부과할 수 없음 - 신뢰 점수 감점으로 반영)."""
        hold = await self.hold_repo.get_by_care_session(care_session.id)
        if hold is None or hold.status != PointHoldStatus.HELD:
            return

        if care_session.at_fault_user_id == care_session.requester_id:
            await self._forfeit_hold(hold, NO_SHOW_PENALTY_REASON)
        else:
            await self._release_hold(hold)
        hold.resolved_at = care_session.cancelled_at

        await self.session.commit()

    async def settle_care_session(self, care_session: CareSession) -> PointTransaction | None:
        if await self.ledger_repo.has_settled(CARE_SESSION_REFERENCE_TYPE, care_session.id):
            return None

        raw_slots = (care_session.actual_minutes or 0) // SLOT_MINUTES
        hold = await self.hold_repo.get_by_care_session(care_session.id)

        if hold is None or hold.status != PointHoldStatus.HELD:
            if raw_slots <= 0:
                return None
            return await self._transfer(
                payer_id=care_session.requester_id,
                payee_id=care_session.provider_id,
                amount=raw_slots,
                reason=SETTLEMENT_REASON,
                reference_type=CARE_SESSION_REFERENCE_TYPE,
                reference_id=care_session.id,
            )

        slots = min(raw_slots, hold.amount)
        payer_account = await self.account_repo.get_or_create(hold.payer_id)
        payer_account.balance += hold.amount - slots
        payer_account.held_balance -= hold.amount
        hold.status = PointHoldStatus.SETTLED
        hold.resolved_at = care_session.checkout_at

        if slots <= 0:
            await self.session.commit()
            return None

        payee_account = await self.account_repo.get_or_create(hold.payee_id)
        transaction = PointTransaction(
            reason=SETTLEMENT_REASON, reference_type=CARE_SESSION_REFERENCE_TYPE, reference_id=care_session.id
        )
        self.ledger_repo.add_transaction(transaction)
        await self.session.flush()

        self.ledger_repo.add_entry(
            PointEntry(
                transaction_id=transaction.id, user_id=hold.payer_id, counterparty_id=hold.payee_id, amount=-slots
            )
        )
        self.ledger_repo.add_entry(
            PointEntry(
                transaction_id=transaction.id, user_id=hold.payee_id, counterparty_id=hold.payer_id, amount=slots
            )
        )
        payee_account.balance += slots

        await self.session.commit()
        await self.session.refresh(transaction)
        return transaction
