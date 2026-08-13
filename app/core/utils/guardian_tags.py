"""REQ-F-ACC-04 보유 태그 코드 목록. 선택 6종은 요구사항정의서에 미확정 — 알려진 예시만
우선 등록하고, 값은 DB Enum이 아닌 문자열이라 마이그레이션 없이 추가할 수 있다
(`docs/tasks/T-ACC-2.md` 가정 참고).

MAT 하드필터(REQ-F-MAT-03) 완화불가 4종은 전부 여기 등록된다: `ALLERGY_RESPONSE`/
`MEDICATION_MANAGEMENT`는 요청자 아동의 `ChildSensitiveInfo` 존재 여부로 필요성이
트리거되는 "보호자가 대응 가능함"을 뜻하는 태그이고(`docs/tasks/T-MAT-1.md` 가정 참고),
`FIRST_AID_CERTIFIED`/`NON_SMOKING_HOUSEHOLD`는 상시 필수다.
"""

MANDATORY_GUARDIAN_TAG_CODES = frozenset(
    {
        "ALLERGY_RESPONSE",  # 알레르기 대응 (완화불가 4종, 아동 알레르기 있을 때만 트리거)
        "MEDICATION_MANAGEMENT",  # 투약 관리 (완화불가 4종, 아동 투약 있을 때만 트리거)
        "FIRST_AID_CERTIFIED",  # 응급처치 이수 (완화불가 4종, 상시 필수)
        "NON_SMOKING_HOUSEHOLD",  # 비흡연 가정 (완화불가 4종, 상시 필수)
    }
)

KNOWN_GUARDIAN_TAG_CODES = MANDATORY_GUARDIAN_TAG_CODES | frozenset(
    {
        "HAS_VEHICLE",  # 차량 보유
    }
)
