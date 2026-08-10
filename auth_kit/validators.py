"""입력값 검증/정규화. Pydantic AfterValidator로 붙여 쓴다.

4개 레포에 거의 같은 코드가 복붙돼 있었고, 그중 서로 어긋난 부분(대문자 요구 여부,
정규화 누락)만 정리했다. 여기 있는 함수는 DB를 모른다 - 중복확인은 service.py 담당.
"""

import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Any, TypeVar

from dateutil.relativedelta import relativedelta
from pydantic import AfterValidator

from security_kit.crypto import mask_email as _mask_email
from security_kit.crypto import sanitize_credential as _sanitize_credential

from . import config

T = TypeVar("T")

# 010-1234-5678 / 01012345678 / +821012345678 (010 외 국번은 이미 신규 발급이 없다)
_PHONE_PATTERNS = (r"010-\d{4}-\d{4}", r"010\d{8}", r"\+8210\d{8}")


def optional(func: Callable[..., Any]) -> AfterValidator:
    """None을 그대로 통과시키는 선택 입력용 래퍼."""

    def _validate(v: T | None) -> T | None:
        return func(v) if v is not None else v

    return AfterValidator(_validate)


def validate_password(password: str) -> str:
    if len(password) < config.PASSWORD_MIN_LENGTH:
        raise ValueError(f"비밀번호는 {config.PASSWORD_MIN_LENGTH}자 이상이어야 합니다.")

    required = [(r"[a-z]", "영문 소문자"), (r"[0-9]", "숫자"), (r"[^a-zA-Z0-9]", "특수문자")]
    if config.PASSWORD_REQUIRE_UPPERCASE:
        required.insert(0, (r"[A-Z]", "영문 대문자"))

    missing = [label for pattern, label in required if not re.search(pattern, password)]
    if missing:
        # 어떤 종류가 빠졌는지 알려준다 - "규칙에 맞지 않습니다"만 주면 사용자가 8자 이상인데
        # 왜 안 되는지 알 수 없어서 계속 같은 비밀번호를 다시 넣는다.
        raise ValueError(f"비밀번호에 {', '.join(missing)}를 포함해주세요.")
    return password


def normalize_email(email: str) -> str:
    """저장·조회 양쪽에서 항상 이걸 통과시킨다.

    모바일 자동 대문자화나 복붙 공백 때문에 " Test@x.com "과 "test@x.com"이 별개 계정으로
    갈리면, 가입은 되는데 로그인이 안 되는(중복 계정) 문제가 생긴다. DB에서 func.lower()로
    비교하는 방식은 저장값 자체가 정규화돼 있지 않으면 공백 차이를 못 막는다.
    """
    return email.strip().lower()


def validate_phone_number(phone_number: str) -> str:
    if not any(re.fullmatch(p, phone_number) for p in _PHONE_PATTERNS):
        raise ValueError("휴대폰 번호 형식이 올바르지 않습니다. (예: 010-1234-5678)")
    return phone_number


def normalize_phone_number(phone_number: str) -> str:
    """`01012345678` 형태로 통일한다. 형식 검증은 validate_phone_number가 먼저 한다고 가정."""
    digits = re.sub(r"\D", "", phone_number)
    return "0" + digits[2:] if digits.startswith("8210") else digits


def validate_nickname(nickname: str) -> str:
    if not re.fullmatch(r"[가-힣a-zA-Z0-9]{2,12}", nickname):
        raise ValueError("닉네임은 한글/영문/숫자 2~12자로 입력해주세요.")
    return nickname


def validate_birth_date(birth_date: date | str) -> date:
    """형식 + 만 MIN_SIGNUP_AGE세 이상 + 미래 날짜 아님까지 한 번에 본다."""
    if isinstance(birth_date, str):
        try:
            birth_date = date.fromisoformat(birth_date)
        except ValueError as e:
            raise ValueError("날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)") from e

    today = datetime.now(tz=config.TIMEZONE).date()
    if birth_date > today:
        raise ValueError("생년월일이 미래일 수 없습니다.")
    if birth_date > today - relativedelta(years=config.MIN_SIGNUP_AGE):
        raise ValueError(f"서비스 약관에 따라 만 {config.MIN_SIGNUP_AGE}세 미만은 회원가입이 불가합니다.")
    return birth_date


# 자격증명 정리와 이메일 마스킹은 보안 모듈이 단일 출처다(로그 마스킹 등 다른 곳에서도 쓴다).
sanitize_credential = _sanitize_credential
mask_email = _mask_email
