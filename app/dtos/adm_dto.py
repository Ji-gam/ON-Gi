from pydantic import BaseModel, Field


class CoreMetricsResponse(BaseModel):
    """REQ-F-ADM-02. `hypothesis_events`를 원천으로 산출하는 지표 3종(목표값은 요구사항정의서 §4)."""

    candidate_availability_rate: float = Field(
        description="상보 후보 보유율(목표 60%) — 후보가 1건이라도 노출된 사용자 비율"
    )
    l2_to_l3_transition_rate: float = Field(description="L2→L3 전이율(목표 10%) — L2 도달 관계 중 L3까지 간 비율")
    rematch_rate: float = Field(description="재매칭률(목표 30%) — 전체 돌봄 요청 중 재요청(REMATCH_REQUESTED) 비율")


class SuspendRequest(BaseModel):
    reason: str


class SuspendedSessionResponse(BaseModel):
    session_id: int
    counterparty_id: int
