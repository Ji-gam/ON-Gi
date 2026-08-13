"""REQ-F-MAT-05. 종합 점수 가중치 - 가치관 유사도 35% + 상보 스코어 35% + 나머지 30%
(거리·개월수 유사도·신뢰점수 각 10%). AGENTS.md §6 "결정됨" 항목 - 값 자체를 바꾸려면
반드시멈춤. 설정파일화+변경이력(REQ-F-MAT-05 후반부)은 `docs/tasks/T-MAT-1.md` 가정 참고,
후속 Task(ADM 도메인)로 미룬다. 신뢰점수 자체 산식의 가중치는 T-TRS-1
(`app/repositories/trust_weight_repository.py`) 범위 - 여기 WEIGHT_TRUST는 매칭 총점 내에서
신뢰점수가 차지하는 비중일 뿐이다.
"""

WEIGHT_VALUES_SIMILARITY = 0.35
WEIGHT_COMPLEMENTARY = 0.35
WEIGHT_DISTANCE = 0.10
WEIGHT_AGE_SIMILARITY = 0.10
WEIGHT_TRUST = 0.10

MAX_DISTANCE_M = 1000.0
MAX_AGE_DIFF_MONTHS = 24.0
