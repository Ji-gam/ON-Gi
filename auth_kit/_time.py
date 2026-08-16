"""시간 유틸. service.py/verification_service.py가 공유한다."""

from datetime import datetime
from typing import overload

from . import config


def now() -> datetime:
    return datetime.now(tz=config.TIMEZONE)


@overload
def aware(value: datetime) -> datetime: ...
@overload
def aware(value: None) -> None: ...
def aware(value: datetime | None) -> datetime | None:
    """MySQL(asyncmy)은 DATETIME을 타임존 없이(naive) 돌려준다 - tz-aware 값과 비교하면
    TypeError가 나므로 비교 전에 항상 이걸 통과시킨다."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=config.TIMEZONE)
    return value
