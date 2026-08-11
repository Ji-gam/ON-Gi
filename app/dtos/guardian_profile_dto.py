"""보호자(User) 프로필 요청/응답 DTO (REQ-F-ACC-04)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.guardian_profile import HouseholdComposition, JobCategory, WorkType


class GuardianProfileUpsertRequest(BaseModel):
    residence_h3: Annotated[str, Field(min_length=1, max_length=15, description="H3 셀 문자열(위경도 아님)")]
    job_category: JobCategory
    work_type: WorkType
    household_composition: HouseholdComposition
    tags: Annotated[list[str], Field(default_factory=list, description="보유 태그 코드 목록")]


class GuardianProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    residence_h3: str
    job_category: JobCategory
    work_type: WorkType
    household_composition: HouseholdComposition
    tags: list[str]
    updated_at: datetime
