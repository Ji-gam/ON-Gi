"""security_kit 얇은 래퍼. 구현은 전부 security_kit에 있다.

이 파일이 하는 일은 하나뿐이다: 도메인 무관 보안 함수에 이 프로젝트의 TTL 정책을 붙여
`create_access_token(user_id)` 처럼 인자 없이 부를 수 있게 하는 것.

복사본을 두지 않는 이유: 보안 로직이 두 곳에 있으면 취약점을 고칠 때 한쪽만 고쳐진다.
"""

from datetime import datetime

from security_kit.crypto import (
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
from security_kit.tokens import (
    GOOGLE_ISSUER,
    GOOGLE_JWKS_URL,
    KAKAO_ISSUER,
    KAKAO_JWKS_URL,
    decode,
    issue,
    verify_oidc_id_token,
)

from . import config

# 전화번호는 암호화 컬럼이라 검색이 안 되므로 HMAC 조회 키를 따로 만든다(security_kit 참고).
hash_phone = hash_lookup_value


def create_access_token(user_id: int) -> str:
    return issue("access", config.ACCESS_TOKEN_TTL, sub=str(user_id))


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """(토큰, jti, 만료시각). jti를 DB에 남겨 로테이션/재사용 탐지에 쓴다."""
    from security_kit.tokens import issue_refresh

    return issue_refresh(user_id, config.REFRESH_TOKEN_TTL)


def create_social_signup_token(provider: str, provider_uid: str, email: str | None, name: str | None) -> str:
    """소셜 신규 가입자가 추가정보를 입력하는 동안만 쓰는 임시 토큰. 이 토큰으로는
    일반 API를 호출할 수 없고(typ=social_signup), 계정도 아직 만들어지지 않은 상태다."""
    return issue(
        "social_signup",
        config.SOCIAL_SIGNUP_TOKEN_TTL,
        provider=provider,
        provider_uid=provider_uid,
        email=email,
        name=name,
    )


def create_password_reset_token(user_id: int) -> str:
    return issue("password_reset", config.PASSWORD_RESET_TTL, sub=str(user_id))


def new_otp_code() -> str:
    """6자리 휴대폰 본인확인 코드(REQ-F-ACC-01). 저장은 `hash_token`으로 해시해서만."""
    import secrets

    return f"{secrets.randbelow(1000000):06d}"


def random_nickname() -> str:
    """소셜/게스트 가입자가 닉네임을 안 줄 때 쓰는 임시 닉네임. 사용자가 나중에 바꾼다."""
    import base64
    import os

    return "사용자" + base64.b32encode(os.urandom(5)).decode().rstrip("=").lower()


__all__ = [
    "EncryptedStr",
    "GOOGLE_ISSUER",
    "GOOGLE_JWKS_URL",
    "KAKAO_ISSUER",
    "KAKAO_JWKS_URL",
    "constant_time_equals",
    "create_access_token",
    "create_password_reset_token",
    "create_refresh_token",
    "create_social_signup_token",
    "decode",
    "hash_password",
    "hash_phone",
    "hash_token",
    "mask_email",
    "mask_phone",
    "needs_rehash",
    "new_nonce",
    "new_otp_code",
    "new_secret",
    "new_url_token",
    "random_nickname",
    "redact",
    "sanitize_credential",
    "verify_oidc_id_token",
    "verify_password",
]
