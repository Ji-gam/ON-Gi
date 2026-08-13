"""회원가입/인증 드롭인 모듈.

사용:
    from auth_kit.models import Base            # Alembic target_metadata = Base.metadata
    from auth_kit.router import auth_router, get_session
    app.include_router(auth_router, prefix="/api/v1")
    app.dependency_overrides[get_session] = my_get_session
"""

from .models import AuthProvider, Base, Gender, OnboardingStatus, User
from .service import AuthResult, AuthService, SocialProfile
from .terms_catalog import TERMS_CATALOG, TermsType

__all__ = [
    "AuthProvider",
    "AuthResult",
    "AuthService",
    "Base",
    "Gender",
    "OnboardingStatus",
    "SocialProfile",
    "TERMS_CATALOG",
    "TermsType",
    "User",
]
