"""REQ-F-MAT-05. 종합 점수 가중치 - 가치관 유사도 35% + 상보 스코어 35% + 나머지 30%
(거리·개월수 유사도·신뢰점수 각 10%). AGENTS.md §6 "결정됨" 항목 - 값 자체를 바꾸려면
반드시멈춤. 설정파일화+변경이력(REQ-F-MAT-05 후반부)은 `docs/tasks/T-MAT-1.md` 가정 참고,
후속 Task(ADM 도메인)로 미룬다.
"""

WEIGHT_VALUES_SIMILARITY = 0.35
WEIGHT_COMPLEMENTARY = 0.35
WEIGHT_DISTANCE = 0.10
WEIGHT_AGE_SIMILARITY = 0.10
WEIGHT_TRUST = 0.10

MAX_DISTANCE_M = 1000.0
MAX_AGE_DIFF_MONTHS = 24.0
STUB_TRUST_SCORE = 0.5  # TRS 도메인 미구현 - 완성 후 실제 점수로 교체
