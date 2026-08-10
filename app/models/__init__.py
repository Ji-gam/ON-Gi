# 도메인 모델을 여기에 임포트해 Base.metadata에 등록한다(Alembic autogenerate 대상).
import auth_kit.models  # noqa: F401  # users/social_accounts/terms_agreements 등 (auth_kit 소유)
from app.models.base import Base
from app.models.children import Child, ChildSensitiveInfo  # noqa: F401  # ACC (REQ-F-ACC-05/06)

__all__ = ["Base", "Child", "ChildSensitiveInfo"]
