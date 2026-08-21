"""REQ-F-COM-01. 채팅 메시지의 연락처 패턴을 경고 후 마스킹한다.
# ponytail: 휴대폰 번호 정규식만 커버(요구사항 검증 기준이 "휴대폰 번호 형식"으로 명시된 항목).
주소 등 다른 식별정보 패턴은 검증 기준이 없어 범위 밖 - 필요해지면 패턴을 추가한다.
"""

import re

_PHONE_PATTERN = re.compile(r"01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}")


def mask_pii(text: str) -> tuple[str, bool]:
    """연락처 패턴이 있으면 숫자를 `*`로 마스킹한 텍스트와 경고 여부를 반환한다."""
    if not _PHONE_PATTERN.search(text):
        return text, False
    masked = _PHONE_PATTERN.sub(lambda m: re.sub(r"\d", "*", m.group()), text)
    return masked, True
