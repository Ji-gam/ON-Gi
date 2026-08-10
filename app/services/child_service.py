from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.children import Child, ChildGender, ChildSensitiveInfo
from app.repositories.child_repository import ChildRepository
from auth_kit.models import TermsAgreement, User
from auth_kit.terms_catalog import TermsType


class ChildService:
    """REQ-F-ACC-05/06. 아동 등록/조회. 법정대리인 동의(REQ-F-ACC-03)는 가입이 아니라
    이 서비스가 아동 정보 입력 직전에 확인한다 - 별도 화면에서 먼저 받아야 한다."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ChildRepository(session)

    async def _assert_guardian_consent(self, user_id: int) -> None:
        row = await self.session.scalar(
            select(TermsAgreement).where(
                TermsAgreement.user_id == user_id, TermsAgreement.terms_type == str(TermsType.GUARDIAN_CONSENT)
            )
        )
        if row is None or not row.is_active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "법정대리인 동의가 필요합니다. 아동 정보를 입력하기 전에 동의를 먼저 완료해주세요.",
            )

    async def create_child(
        self,
        user: User,
        *,
        months_old: int,
        gender: ChildGender,
        temperament_memo: str | None,
        allergies: str | None,
        conditions: str | None,
        medications: str | None,
    ) -> Child:
        await self._assert_guardian_consent(user.id)

        child = Child(user_id=user.id, months_old=months_old, gender=gender, temperament_memo=temperament_memo)
        self.repo.add(child)
        await self.session.flush()  # child.id 확보

        if allergies or conditions or medications:
            self.session.add(
                ChildSensitiveInfo(
                    child_id=child.id, allergies=allergies, conditions=conditions, medications=medications
                )
            )
        await self.session.commit()
        await self.session.refresh(child)
        return child

    async def list_children(self, user: User) -> list[Child]:
        return await self.repo.list_by_user(user.id)

    async def _get_owned(self, user: User, child_id: int) -> Child:
        child = await self.repo.get(child_id)
        if child is None or child.user_id != user.id:
            # 소유자가 아니면 존재 자체를 알려주지 않는다(다른 보호자의 아동 목록을 열거하는 것을 방지).
            raise HTTPException(status.HTTP_404_NOT_FOUND, "아동 정보를 찾을 수 없습니다.")
        return child

    async def get_child(self, user: User, child_id: int) -> Child:
        return await self._get_owned(user, child_id)

    async def delete_child(self, user: User, child_id: int) -> None:
        child = await self._get_owned(user, child_id)
        await self.repo.delete(child)
        await self.session.commit()
