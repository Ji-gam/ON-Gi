"""회원가입/인증 정책 상수. 프로젝트마다 다른 값은 환경변수로 뺐다.

정책 값을 코드 여기저기 흩지 않고 한 파일에 모은 이유: 4개 레포에서 같은 정책(비번 규칙,
잠금 횟수, 만14세)이 서로 다른 파일에 조금씩 다른 값으로 박혀 있어서, "우리 비번 정책이
뭐였지"를 확인하려면 3곳을 봐야 했다.

비밀값·쿠키 설정은 security_kit.config가 단일 출처다 - 여기서 재수출만 한다.
"""

import os
from datetime import timedelta

from security_kit.config import (
    TIMEZONE,
    cookie_domain,
    cookie_secure,
    jwt_secret,
    pii_encryption_key,
    pii_hash_key,
)

__all__ = [
    "ACCESS_TOKEN_TTL",
    "EMAIL_VERIFICATION_TTL",
    "FRONTEND_BASE_URL",
    "LOCKOUT_DURATION",
    "MAX_LOGIN_ATTEMPTS",
    "MIN_SIGNUP_AGE",
    "PASSWORD_MIN_LENGTH",
    "PASSWORD_REQUIRE_UPPERCASE",
    "PASSWORD_RESET_TTL",
    "PHONE_VERIFICATION_TTL",
    "REFRESH_TOKEN_TTL",
    "SOCIAL_SIGNUP_TOKEN_TTL",
    "TIMEZONE",
    "WITHDRAWAL_GRACE",
    "cookie_domain",
    "cookie_secure",
    "google_client_id",
    "jwt_secret",
    "kakao_app_key",
    "pii_encryption_key",
    "pii_hash_key",
    "require_email_verification",
    "require_phone_verification",
]

# ── 비밀번호 ────────────────────────────────────────────────────────────────
PASSWORD_MIN_LENGTH = 8
# 대문자까지 요구할지. 4개 레포 중 3개가 요구했고 1개가 빼서 정책이 갈렸다 - 기본은 요구(강한 쪽).
PASSWORD_REQUIRE_UPPERCASE = True

# ── 가입 자격 ───────────────────────────────────────────────────────────────
# 개인정보보호법상 만14세 미만은 법정대리인 동의가 필요하다. 대리인 동의 흐름을 만들 여력이
# 없으면 이 나이 미만을 아예 막는 게 맞다(4개 레포 전부 그렇게 했다).
MIN_SIGNUP_AGE = 14


def require_email_verification() -> bool:
    """이메일 인증(메일 링크 클릭)을 가입 전제조건으로 강제할지."""
    return os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() == "true"


EMAIL_VERIFICATION_TTL = timedelta(minutes=30)
PASSWORD_RESET_TTL = timedelta(minutes=30)


def require_phone_verification() -> bool:
    """휴대폰 본인확인(REQ-F-ACC-01)을 가입 전제조건으로 강제할지."""
    return os.getenv("REQUIRE_PHONE_VERIFICATION", "true").lower() == "true"


PHONE_VERIFICATION_TTL = timedelta(minutes=5)  # OTP 유효시간. 이메일 인증보다 짧게 - 재전송이 쉬워서.

# ── 로그인 시도 제한(브루트포스 방어) ────────────────────────────────────────
# 실제 잠금 판정 로직은 security_kit.guards.LockoutPolicy에 있다.
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

# ── 토큰 ────────────────────────────────────────────────────────────────────
ACCESS_TOKEN_TTL = timedelta(minutes=30)
REFRESH_TOKEN_TTL = timedelta(days=14)
# 소셜 신규 가입자가 추가정보(닉네임/생년월일/동의)를 입력하는 동안만 유효한 임시 토큰.
SOCIAL_SIGNUP_TOKEN_TTL = timedelta(minutes=10)

# ── 회원탈퇴 ────────────────────────────────────────────────────────────────
# 유예기간 안에는 탈퇴 취소가 가능하고, 지나면 purge_deactivated()가 물리 삭제한다.
# timedelta(0)으로 두면 유예 없이 즉시 완전 삭제(개인정보 지체없는 파기)로 동작한다.
WITHDRAWAL_GRACE = timedelta(days=30)


# ── 소셜 로그인 ─────────────────────────────────────────────────────────────
def google_client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "")


def kakao_app_key() -> str:
    return os.getenv("KAKAO_NATIVE_APP_KEY", "")


# 약관 URL을 만드는 데 import 시점에 필요하다(비밀값이 아니라 상수로 둔다).
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
