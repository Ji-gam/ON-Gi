"""REQ-F-MAT-06, REQ-NF-AVA-01. 추천 근거 문장 생성 - 규칙 기반 폴백.

LLM+RAG 근거문장(ai_worker)은 아직 붙지 않았으므로, 우선 이미 계산된 하위 지표
(거리·상보스코어·가치관유사도·신뢰점수)를 임계값으로 조합한 한국어 문장을 반환한다.
REQ-NF-AVA-01이 요구하는 "외부 LLM API 장애 시 규칙 기반 대체 문구" 자체가 이 함수이며,
추후 LLM 문장이 추가되어도 실패 시 이 함수로 폴백한다.
"""

_DISTANCE_NEAR_M = 300.0
_COMPLEMENTARY_HIGH = 0.5
_VALUES_HIGH = 0.5
_TRUST_HIGH = 0.6


def build_recommendation_reason(
    *,
    distance_m: float,
    complementary_score: float,
    values_similarity: float,
    trust_score: float,
    tags_satisfied: bool = True,
) -> str:
    facts: list[str] = []

    if distance_m <= _DISTANCE_NEAR_M:
        facts.append("거주지가 도보권으로 가깝다")
    else:
        facts.append(f"거주지가 {int(distance_m)}m 이내로 가깝다")

    if complementary_score >= _COMPLEMENTARY_HIGH:
        facts.append("근무 시간이 정확히 엇갈린다")

    if tags_satisfied:
        facts.append("필수 돌봄 조건을 충족한다")

    if values_similarity >= _VALUES_HIGH:
        facts.append("양육관이 가깝다")

    if trust_score >= _TRUST_HIGH:
        facts.append("신뢰 점수가 높다")

    return " · ".join(facts) + "."
