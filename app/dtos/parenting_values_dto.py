"""양육 가치관 진단 요청/응답 DTO (REQ-F-ACC-07/08/10)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.utils.baumrind_questions import ParentingTypeLabel


class BaumrindQuestionItem(BaseModel):
    """`GET /acc/parenting-values/questions`용 - 프런트가 문항 텍스트를 하드코딩하지 않게 한다."""

    index: int
    text: str
    dimension: str


class QuestionnaireSubmitRequest(BaseModel):
    answers: Annotated[
        list[int], Field(min_length=8, max_length=8, description="문항 8개에 대한 1~5점 응답, 순서 고정")
    ]


class NarrativeSubmitRequest(BaseModel):
    narrative: Annotated[str, Field(min_length=1, max_length=2000, description="자유 서술 양육 경험")]


class ParentingValuesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    warmth_score: float
    control_score: float
    type_label: ParentingTypeLabel
    narrative: str | None
    updated_at: datetime
