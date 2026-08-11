from pydantic import BaseModel, Field


class CandidateResponse(BaseModel):
    user_id: int
    nickname: str
    total_score: float = Field(description="가중합산 종합 점수, 0~1")
    values_similarity: float = Field(description="가치관 유사도(35% 가중치 반영 전 원점수), 0~1")
    complementary_score: float = Field(description="상보 스코어(35% 가중치 반영 전 원점수), 0~1")
    distance_m: float = Field(description="거주지 간 실거리(m)")
    age_similarity: float = Field(description="아동 개월 수 유사도, 0~1")
    trust_score: float = Field(description="신뢰 점수(TRS 도메인 미구현 - 스텁 고정값)")
