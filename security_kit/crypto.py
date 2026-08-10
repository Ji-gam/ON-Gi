"""비밀번호 해시 / 토큰 해시 / 개인정보 암호화. 전부 순수함수라 DB 없이 단독 테스트된다.

비밀번호는 stdlib `hashlib.scrypt`를 쓴다 - bcrypt·argon2 패키지를 추가로 깔지 않아도 되고
scrypt는 정식 KDF다. 해시 문자열에 알고리즘·파라미터를 박아두므로(`scrypt$n$r$p$salt$hash`)
나중에 파라미터를 올리거나 argon2로 갈아탈 때 로그인 시점에 점진적으로 재해시할 수 있다.
"""

import base64
import hashlib
import hmac
import re
import secrets
from typing import Any

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from . import config

# ── 비밀번호 ────────────────────────────────────────────────────────────────
# n=2**14 → 약 16MB 메모리. 로그인 경로에서 체감되지 않고, GPU 대량 크래킹에는 충분히 비싸다.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """해시 형식이 깨져 있어도 예외를 던지지 않고 False를 준다.

    로그인 경로가 500을 내면 (1) 사용자는 원인을 알 수 없고 (2) 공격자는 "이 계정의 해시가
    이상하다"는 정보를 얻는다. 인증 실패로 일관되게 처리한다.
    """
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(hash_b64)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected, actual)


def needs_rehash(stored: str) -> bool:
    """파라미터가 현재 기준보다 약하면 True.

    쓰는 법: 로그인이 성공한 직후 이 값이 True면 방금 받은 평문으로 다시 해시해 저장한다.
    그 순간이 평문을 합법적으로 들고 있는 유일한 시점이라, 일괄 마이그레이션이 불가능하다.
    """
    try:
        scheme, n, r, p, _, _ = stored.split("$")
    except ValueError:
        return True
    return scheme != "scrypt" or (int(n), int(r), int(p)) != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P)


# ── 랜덤 / 비교 ─────────────────────────────────────────────────────────────
def new_url_token(nbytes: int = 32) -> str:
    """이메일 인증·비밀번호 재설정 링크에 넣는 토큰. `random` 모듈은 예측 가능하므로 금지."""
    return secrets.token_urlsafe(nbytes)


def new_nonce(nbytes: int = 24) -> str:
    return secrets.token_urlsafe(nbytes)


def new_secret(nbytes: int = 48) -> str:
    """JWT_SECRET 같은 서버 비밀값 생성용. 배포 전에 한 번 만들어 환경변수에 넣는다."""
    return secrets.token_urlsafe(nbytes)


def constant_time_equals(a: str, b: str) -> bool:
    """토큰·서명·인증코드 비교는 반드시 이걸 쓴다.

    `a == b`는 첫 불일치 문자에서 즉시 반환하므로, 응답 시간 차이로 값을 한 글자씩
    알아낼 수 있다(타이밍 공격). 6자리 인증코드 비교에서 특히 현실적인 위험이다.
    """
    return hmac.compare_digest(a.encode(), b.encode())


# ── 해시 (되돌릴 필요 없는 값) ──────────────────────────────────────────────
def hash_token(token: str) -> str:
    """DB에 토큰 원문을 두지 않기 위한 해시. DB가 유출돼도 유효한 링크를 만들 수 없다.

    `new_url_token()`처럼 엔트로피가 이미 충분한 랜덤값에만 쓴다 - 비밀번호처럼 사람이
    고른 값에는 절대 쓰지 말 것(전수조사로 뚫린다). 그건 hash_password()가 할 일이다.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def hash_lookup_value(value: str) -> str:
    """전화번호·주민번호처럼 "암호화해서 보관하지만 검색은 해야 하는" 값의 조회 키.

    단순 sha256을 쓰면 안 된다: 전화번호는 경우의 수가 1억 수준이라 전수조사로 즉시
    복원된다. 서버만 아는 키를 섞은 HMAC이라야 유출된 해시에서 원문을 못 되돌린다.
    """
    key = config.pii_hash_key()
    if not key:
        raise RuntimeError("PII_HASH_KEY 환경변수가 필요합니다. security_kit.crypto.new_secret()로 생성하세요.")
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()


# ── 개인정보 암호화 컬럼 ────────────────────────────────────────────────────
def _fernet() -> Any:
    from cryptography.fernet import Fernet  # 이 컬럼을 실제로 쓰는 프로젝트만 의존성이 필요하다

    key = config.pii_encryption_key()
    if not key:
        raise RuntimeError("PII_ENCRYPTION_KEY 환경변수가 필요합니다. Fernet.generate_key()로 생성하세요.")
    return Fernet(key.encode())


class EncryptedStr(TypeDecorator):
    """저장 시 암호화, 조회 시 복호화하는 SQLAlchemy 컬럼 타입.

    이름·전화번호·주소처럼 유출 피해가 큰 값에 쓴다. 키가 없으면 조용히 평문으로
    저장되는 일 없이 에러가 난다.

    제약: 이 컬럼은 `WHERE = `·정렬·`LIKE`가 불가능하다(같은 값도 매번 다른 암호문이 된다).
    검색이 필요하면 hash_lookup_value()로 만든 해시 컬럼을 나란히 둔다.

    키 교체(rotation): Fernet은 MultiFernet으로 다중 키를 지원한다. 교체가 필요해지면
    _fernet()을 MultiFernet([new, old])로 바꾸고 배치로 재저장한다.
    """

    impl = String(512)  # 암호문은 원문보다 길다. 원문 100자 기준 여유값.
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        return None if value is None else _fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        return None if value is None else _fernet().decrypt(value.encode()).decode()


# ── 입력 정리 / 마스킹 ──────────────────────────────────────────────────────
_INVISIBLE = re.compile(r"[​-‍﻿]")


def sanitize_credential(value: str) -> str:
    """복붙 시 눈에 안 보이게 딸려오는 zero-width 문자와 앞뒤 공백을 제거한다.

    가입은 타이핑, 로그인은 메모앱 복붙으로 하면 육안으로 같아 보여도 문자열이 달라
    해시가 안 맞는다. 프론트에서도 하되 서버가 최종 방어선이다.
    """
    return _INVISIBLE.sub("", value).strip()


def mask_email(email: str) -> str:
    """`hongildong@x.com` → `hon*******@x.com`. 아이디 찾기 응답·로그에 쓴다."""
    local, _, domain = email.partition("@")
    visible = local[:3] if len(local) > 3 else local[:1]
    return f"{visible}{'*' * max(3, len(local) - len(visible))}@{domain}"


def mask_phone(phone: str) -> str:
    """`01012345678` → `010****5678`. 로그·화면 표시용."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return "*" * len(digits)
    return f"{digits[:3]}{'*' * (len(digits) - 7)}{digits[-4:]}"


def redact(text: str) -> str:
    """로그로 나갈 문자열에서 이메일·전화번호를 마스킹한다.

    예외 메시지나 요청 본문을 그대로 로그에 남기면 개인정보가 로그 수집 시스템(외부 SaaS
    포함)으로 흘러간다. 로그 포맷터에 걸어두거나 logger 호출부에서 감싼다.
    """
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", lambda m: mask_email(m.group()), text)
    return re.sub(r"\b01[016-9][-\s]?\d{3,4}[-\s]?\d{4}\b", lambda m: mask_phone(m.group()), text)
