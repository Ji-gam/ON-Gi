from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.point_ledger import PointEntry, PointTransaction


class PointLedgerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add_transaction(self, transaction: PointTransaction) -> None:
        self.session.add(transaction)

    def add_entry(self, entry: PointEntry) -> None:
        self.session.add(entry)

    async def has_settled(self, reference_type: str, reference_id: int) -> bool:
        result = await self.session.execute(
            select(PointTransaction.id).where(
                PointTransaction.reference_type == reference_type, PointTransaction.reference_id == reference_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_entries_for_user(self, user_id: int) -> list[tuple[PointEntry, PointTransaction]]:
        result = await self.session.execute(
            select(PointEntry, PointTransaction)
            .join(PointTransaction, PointTransaction.id == PointEntry.transaction_id)
            .where(PointEntry.user_id == user_id)
            .order_by(PointTransaction.created_at.desc(), PointEntry.id.desc())
        )
        return [(row.PointEntry, row.PointTransaction) for row in result.all()]
