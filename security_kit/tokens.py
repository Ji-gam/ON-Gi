"""JWT 발급/검증 + 소셜 OIDC ID token 검증.

핵심 규칙 두 개:
1. 모든 토큰에 `typ`을 박고 검증할 때 기대 타입을 명시한다. 이게 없으면 refresh token이나
   비밀번호 재설정 토큰을 Authorization 헤더에 그대로 넣어 일반 API를 호출할 수 있다.
2. 서버 비밀키는 32바이트 이상을 강제한다. 짧으면 실행 시점에 막는다(경고로 넘기지 않는다).
"""

import asyncio
import hmac
import uuid
from datetime import datetime, timedelta
from typing import Any

import jwt

from . import config

ALGORITHM = "HS256"


def _secret() -> str:
    secret = config.jwt_secret()
    if not secret:
        raise RuntimeError("JWT_SECRET 환경변수가 필요합니다. security_kit.crypto.new_secret()로 생성하세요.")
    if len(secret.encode()) < config.MIN_SECRET_BYTES:
        raise RuntimeError(
            f"JWT_SECRET이 너무 짧습니다({len(secret.encode())}바이트). "
            f"{config.MIN_SECRET_BYTES}바이트 이상으로 설정하세요."
        )
    return secret


def issue(typ: str, ttl: timedelta, **claims: Any) -> str:
    """`typ`과 만료를 강제로 넣어 토큰을 만든다. ttl은 호출부가 정한다(정책은 도메인의 몫)."""
    now = config.now()
    payload = {**claims, "typ": typ, "iat": int(now.timestamp()), "exp": int((now + ttl).timestamp())}
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode(token: str, expected_typ: str) -> dict[str, Any]:
    """만료·위조·타입 불일치를 모두 `jwt.InvalidTokenError`로 통일해서 던진다.

    호출부는 이 예외 하나만 잡아 401로 바꾸면 된다. 예외 종류에 따라 다른 메시지를 주면
    "토큰이 만료됨" vs "서명이 틀림"이 구분되어 공격자에게 정보를 준다.
    """
    payload: dict[str, Any] = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    if payload.get("typ") != expected_typ:
        raise jwt.InvalidTokenError(f"토큰 종류가 올바르지 않습니다: {payload.get('typ')} != {expected_typ}")
    return payload


def issue_access(subject: str | int, ttl: timedelta, **claims: Any) -> str:
    return issue("access", ttl, sub=str(subject), **claims)


def issue_refresh(subject: str | int, ttl: timedelta) -> tuple[str, str, datetime]:
    """(토큰, jti, 만료시각).

    jti를 DB에 남겨야 로테이션과 재사용 탐지가 가능하다. 토큰 원문은 저장하지 않는다 -
    jti만 있으면 "이 토큰이 이미 폐기됐는지" 판정에 충분하다.
    """
    jti = uuid.uuid4().hex
    return issue("refresh", ttl, sub=str(subject), jti=jti), jti, config.now() + ttl


# ── 소셜 OIDC (모바일 앱 SDK 흐름) ──────────────────────────────────────────
GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
KAKAO_ISSUER = "https://kauth.kakao.com"
KAKAO_JWKS_URL = "https://kauth.kakao.com/.well-known/jwks.json"
APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


async def verify_oidc_id_token(id_token: str, nonce: str, issuer: str, audience: str, jwks_url: str) -> dict[str, Any]:
    """공급자 JWKS로 서명을 검증하고 iss/aud/exp/nonce까지 확인한다.

    절대 하지 말 것: ID token을 `jwt.decode(..., options={"verify_signature": False})`로
    payload만 꺼내 쓰기. 그러면 누구나 임의의 sub를 담은 토큰을 만들어 남의 계정으로
    로그인할 수 있다.

    검증 항목이 넷 다 필요한 이유:
    - 서명: 위조 차단
    - aud(우리 앱 ID): 다른 앱용으로 발급된 유효한 토큰을 가져와 쓰는 것 차단
    - iss/exp: 발급자·유효기간
    - nonce: 우리가 이번 로그인에 지정한 값과 일치하는지 → 과거 토큰 재사용 차단

    검증을 통과한 nonce는 반드시 한 번만 쓰이도록 소비해야 한다(guards.NonceStore 참고).
    JWKS 조회는 동기 함수라 to_thread로 감싼다 - 결과는 PyJWKClient가 캐싱한다.
    """

    def _verify() -> dict[str, Any]:
        signing_key = jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(id_token)
        return jwt.decode(id_token, signing_key.key, algorithms=["RS256"], audience=audience, issuer=issuer)

    claims: dict[str, Any] = await asyncio.to_thread(_verify)
    if not nonce or not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise jwt.InvalidTokenError("nonce가 일치하지 않습니다.")
    return claims
