"""REQ-F-MAT-06, REQ-NF-AVA-01: 규칙 기반 추천 근거 문장은 2문장 이내이며,
문장에 담긴 수치가 실제 계산값과 일치해야 한다."""

from app.core.utils.recommendation_reason import build_recommendation_reason


def test_reason_reflects_actual_distance_value_when_not_walkable():
    reason = build_recommendation_reason(
        distance_m=850.0,
        complementary_score=0.1,
        values_similarity=0.1,
        trust_score=0.1,
    )
    assert "850m" in reason
    assert reason.count(".") == 1  # 한 문장(마침표 1개)으로, 2문장 이내 요건을 충족


def test_reason_uses_walkable_phrase_under_threshold():
    reason = build_recommendation_reason(
        distance_m=200.0,
        complementary_score=0.1,
        values_similarity=0.1,
        trust_score=0.1,
    )
    assert "도보권" in reason
    assert "200m" not in reason


def test_reason_adds_clause_per_high_metric():
    low = build_recommendation_reason(
        distance_m=850.0,
        complementary_score=0.1,
        values_similarity=0.1,
        trust_score=0.1,
    )
    high = build_recommendation_reason(
        distance_m=850.0,
        complementary_score=0.9,
        values_similarity=0.9,
        trust_score=0.9,
    )
    assert "근무 시간이 정확히 엇갈린다" in high
    assert "양육관이 가깝다" in high
    assert "신뢰 점수가 높다" in high
    assert "근무 시간이 정확히 엇갈린다" not in low


def test_reason_omits_tags_clause_when_not_satisfied():
    reason = build_recommendation_reason(
        distance_m=850.0,
        complementary_score=0.1,
        values_similarity=0.1,
        trust_score=0.1,
        tags_satisfied=False,
    )
    assert "필수 돌봄 조건을 충족한다" not in reason
