# 도메인 모델을 여기에 임포트해 Base.metadata에 등록한다(Alembic autogenerate 대상).
import auth_kit.models  # noqa: F401  # users/social_accounts/terms_agreements 등 (auth_kit 소유)
from app.models.base import Base
from app.models.children import Child, ChildSensitiveInfo  # noqa: F401  # ACC (REQ-F-ACC-05/06)
from app.models.guardian_profile import GuardianProfile, GuardianTag  # noqa: F401  # ACC (REQ-F-ACC-04)
from app.models.parenting_values import (  # noqa: F401  # ACC (REQ-F-ACC-07/08/10)
    ParentingValuesHistory,
    ParentingValuesProfile,
)
from app.models.work_schedule import WorkSchedule  # noqa: F401  # SCH (REQ-F-SCH-01/03/06)

__all__ = [
    "Base",
    "Child",
    "ChildSensitiveInfo",
    "GuardianProfile",
    "GuardianTag",
    "ParentingValuesHistory",
    "ParentingValuesProfile",
    "WorkSchedule",
]
