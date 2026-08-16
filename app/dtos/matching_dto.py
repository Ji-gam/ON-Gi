from pydantic import BaseModel, Field


class CandidateResponse(BaseModel):
    user_id: int
    nickname: str
    total_score: float = Field(description="가중합산 종합 점수, 0~1")
    values_similarity: float = Field(description="가치관 유사도(35% 가중치 반영 전 원점수), 0~1")
    complementary_score: float = Field(description="상보 스코어(35% 가중치 반영 전 원점수), 0~1")
    distance_m: float = Field(description="거주지 간 실거리(m)")
    age_similarity: float = Field(description="아동 개월 수 유사도, 0~1")
    trust_score: float = Field(description="신뢰 점수(REQ-F-TRS-06/08 가중합), 0~1")
    average_rating: float | None = Field(default=None, description="REQ-F-TRS-07 별점 평균, 평가 없으면 null")
    top_tags: list[str] = Field(default_factory=list, description="REQ-F-TRS-07 후기 태그 상위 3개")
    reason: str = Field(description="REQ-F-MAT-06 추천 근거 문장(규칙 기반), 2문장 이내")
