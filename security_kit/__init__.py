"""도메인 무관 보안 모듈. 회원가입/인증 외의 프로젝트에도 그대로 붙는다.

    from security_kit import hash_password, verify_password, LockoutPolicy, RateLimiter

세 모듈로 나뉜다:
    crypto  - 비밀번호/토큰 해시, 개인정보 암호화 컬럼, 마스킹
    tokens  - JWT 발급·검증(typ 강제), 소셜 OIDC ID token 검증
    guards  - 로그인 잠금, 요청 빈도 제한, 재생 방어, 보안 쿠키/헤더

체크리스트와 적용법은 README.md 참고.
"""

from .crypto import (
    EncryptedStr,
    constant_time_equals,
    hash_lookup_value,
    hash_password,
    hash_token,
    mask_email,
    mask_phone,
    needs_rehash,
    new_nonce,
    new_secret,
    new_url_token,
    redact,
    sanitize_credential,
    verify_password,
)
from .guards import (
    DEFAULT_SECURITY_HEADERS,
    LockoutPolicy,
    LockoutState,
    NonceStore,
    RateLimiter,
    clear_refresh_cookie,
    security_headers_middleware,
    set_refresh_cookie,
)
from .tokens import (
    APPLE_ISSUER,
    APPLE_JWKS_URL,
    GOOGLE_ISSUER,
    GOOGLE_JWKS_URL,
    KAKAO_ISSUER,
    KAKAO_JWKS_URL,
    decode,
    issue,
    issue_access,
    issue_refresh,
    verify_oidc_id_token,
)

__all__ = [
    "APPLE_ISSUER",
    "APPLE_JWKS_URL",
    "DEFAULT_SECURITY_HEADERS",
    "EncryptedStr",
    "GOOGLE_ISSUER",
    "GOOGLE_JWKS_URL",
    "KAKAO_ISSUER",
    "KAKAO_JWKS_URL",
    "LockoutPolicy",
    "LockoutState",
    "NonceStore",
    "RateLimiter",
    "clear_refresh_cookie",
    "constant_time_equals",
    "decode",
    "hash_lookup_value",
    "hash_password",
    "hash_token",
    "issue",
    "issue_access",
    "issue_refresh",
    "mask_email",
    "mask_phone",
    "needs_rehash",
    "new_nonce",
    "new_secret",
    "new_url_token",
    "redact",
    "sanitize_credential",
    "security_headers_middleware",
    "set_refresh_cookie",
    "verify_oidc_id_token",
    "verify_password",
]
