"""REQ-F-CAR-06. 세션당 1건(upsert)인 돌봄 일지. 대상 아동에게 알레르기 정보가 등록돼 있으면
알레르기 항목 미입력 시 저장을 거부한다."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.care_log import CareLog
from app.models.care_session import CareSession, CareSessionStatus
from app.repositories.care_log_repository import CareLogRepository
from app.repositories.care_session_repository import CareSessionRepository
from app.repositories.child_repository import ChildRepository
from auth_kit.models import User


class CareLogService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.session_repo = CareSessionRepository(session)
        self.log_repo = CareLogRepository(session)
        self.child_repo = ChildRepository(session)

    async def _get_accessible_session(self, session_id: int, user: User) -> CareSession:
        care_session = await self.session_repo.get(session_id)
        if care_session is None or user.id not in (care_session.requester_id, care_session.provider_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
        return care_session

    async def upsert(
        self,
        session_id: int,
        provider: User,
        *,
        meal: str | None,
        sleep: str | None,
        mood: str | None,
        note: str | None,
        allergy_note: str | None,
    ) -> CareLog:
        care_session = await self._get_accessible_session(session_id, provider)
        if care_session.provider_id != provider.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
        if care_session.status != CareSessionStatus.CONFIRMED:
            raise HTTPException(status.HTTP_409_CONFLICT, "확정되지 않은 세션입니다.")

        child = await self.child_repo.get(care_session.child_id)
        requires_allergy_note = child is not None and child.sensitive is not None and bool(child.sensitive.allergies)
        if requires_allergy_note and not allergy_note:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "알레르기 등록 아동은 해당 항목을 입력해야 합니다.")

        care_log = await self.log_repo.get(session_id)
        if care_log is None:
            care_log = CareLog(session_id=session_id)
            self.log_repo.add(care_log)

        care_log.meal = meal
        care_log.sleep = sleep
        care_log.mood = mood
        care_log.note = note
        care_log.allergy_note = allergy_note

        await self.session.commit()
        await self.session.refresh(care_log)
        return care_log

    async def get(self, session_id: int, user: User) -> CareLog | None:
        await self._get_accessible_session(session_id, user)
        return await self.log_repo.get(session_id)
