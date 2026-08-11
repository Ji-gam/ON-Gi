from pydantic import BaseModel, ConfigDict, Field


class EvaluationSubmit(BaseModel):
    rating: int = Field(ge=1, le=5, description="별점 1~5")
    tags: list[str] = Field(default_factory=list, description="평가 태그(시간 준수/소통 원활/안전 배려 등)")


class EvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    evaluator_id: int
    evaluatee_id: int
    rating: int


class TrustWeightsUpdate(BaseModel):
    w1: float = Field(description="w1: 별점 가중치")
    w2: float = Field(description="w2: 이행 확인 응답률 가중치")
    w3: float = Field(description="w3: (1-노쇼율) 가중치")
    w4: float = Field(description="w4: 돌봄 일지 작성률 가중치")


class TrustWeightsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    w1: float
    w2: float
    w3: float
    w4: float


class TrustScoreResponse(BaseModel):
    user_id: int
    score: float = Field(description="REQ-F-TRS-08 가중합 신뢰 점수, 0~1")
