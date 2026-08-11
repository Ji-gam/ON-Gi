"""REQ-F-ACC-04 보유 태그 코드 목록. MAT 하드필터(REQ-F-MAT-03) 완화불가 4종 중
`ALLERGY_CARE`/`MEDICATION_MANAGEMENT`는 Child 쪽 데이터에서 파생되므로 여기 없다.
선택 6종은 요구사항정의서에 미확정 — 알려진 예시만 우선 등록하고, 값은 DB Enum이 아닌
문자열이라 마이그레이션 없이 추가할 수 있다(`docs/tasks/T-ACC-2.md` 가정 참고).
"""

KNOWN_GUARDIAN_TAG_CODES = frozenset(
    {
        "FIRST_AID_CERTIFIED",  # 응급처치 이수 (완화불가 4종)
        "NON_SMOKING_HOUSEHOLD",  # 비흡연 가정 (완화불가 4종)
        "HAS_VEHICLE",  # 차량 보유
    }
)
