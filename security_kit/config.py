"""보안 관련 환경변수 접근자 + 시간 유틸.

비밀값을 모듈 상수(`KEY = os.getenv(...)`)로 굳히지 않고 함수로 읽는다. 상수로 두면
python-dotenv로 .env를 나중에 로드하는 흔한 배선에서 값이 조용히 빈 문자열로 남고,
그러면 "키가 없는데 그냥 돌아가는" 상태가 된다.
"""

import os
from datetime import datetime, timedelta, timezone

TIMEZONE = timezone(timedelta(hours=9))  # Asia/Seoul

# RFC 7518 3.2 — HS256 키는 해시 출력 길이(32바이트) 이상이어야 한다.
# 짧은 키는 HS256의 보안 강도를 키 길이까지 끌어내린다.
MIN_SECRET_BYTES = 32


def jwt_secret() -> str:
    return os.getenv("JWT_SECRET", "")


def pii_encryption_key() -> str:
    """`Fernet.generate_key()`로 만든 값. 개인정보 암호화 컬럼에 쓴다."""
    return os.getenv("PII_ENCRYPTION_KEY", "")


def pii_hash_key() -> str:
    """암호화 컬럼은 WHERE 검색이 안 되므로, 조회가 필요한 값은 이 키로 HMAC 해시를 만든다."""
    return os.getenv("PII_HASH_KEY", "")


def cookie_domain() -> str | None:
    return os.getenv("COOKIE_DOMAIN", "") or None


def cookie_secure() -> bool:
    """로컬 http 개발에서만 false. 운영에서 false면 쿠키가 평문으로 전송된다."""
    return os.getenv("COOKIE_SECURE", "true").lower() == "true"


def now() -> datetime:
    return datetime.now(tz=TIMEZONE)


def aware(value: datetime | None) -> datetime | None:
    """MySQL(asyncmy) 등은 DATETIME을 타임존 없이(naive) 돌려준다 - tz-aware 값과 비교하면
    TypeError가 나므로, DB에서 읽은 시각은 비교 전에 항상 이걸 통과시킨다."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=TIMEZONE)
    return value
