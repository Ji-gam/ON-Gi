import h3
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.guardian_tags import KNOWN_GUARDIAN_TAG_CODES
from app.models.guardian_profile import GuardianProfile, HouseholdComposition, JobCategory, WorkType
from app.repositories.guardian_profile_repository import GuardianProfileRepository
from auth_kit.models import User


class GuardianProfileService:
    """REQ-F-ACC-04. 보호자 프로필은 1인당 1건 - 최초 등록/수정 모두 upsert로 처리한다."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GuardianProfileRepository(session)

    def _assert_valid_h3(self, residence_h3: str) -> None:
        if not h3.is_valid_cell(residence_h3):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "유효한 H3 인덱스가 아닙니다.")

    def _assert_known_tags(self, tag_codes: list[str]) -> None:
        unknown = sorted(set(tag_codes) - KNOWN_GUARDIAN_TAG_CODES)
        if unknown:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"알 수 없는 태그 코드: {', '.join(unknown)}")

    async def upsert_profile(
        self,
        user: User,
        *,
        residence_h3: str,
        job_category: JobCategory,
        work_type: WorkType,
        household_composition: HouseholdComposition,
        tags: list[str],
    ) -> tuple[GuardianProfile, list[str]]:
        self._assert_valid_h3(residence_h3)
        self._assert_known_tags(tags)

        profile = await self.repo.get(user.id)
        if profile is None:
            profile = GuardianProfile(user_id=user.id)
            self.session.add(profile)

        profile.residence_h3 = residence_h3
        profile.job_category = job_category
        profile.work_type = work_type
        profile.household_composition = household_composition

        await self.repo.replace_tags(user.id, tags)
        await self.session.commit()
        await self.session.refresh(profile)
        return profile, sorted(set(tags))

    async def get_profile(self, user: User) -> tuple[GuardianProfile, list[str]]:
        profile = await self.repo.get(user.id)
        if profile is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "등록된 보호자 프로필이 없습니다.")
        tags = await self.repo.list_tags(user.id)
        return profile, tags
