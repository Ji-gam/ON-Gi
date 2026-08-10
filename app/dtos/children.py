"""아동(Child) 요청/응답 DTO (REQ-F-ACC-05/06)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.children import ChildGender


class ChildCreateRequest(BaseModel):
    months_old: Annotated[int, Field(ge=0, le=216, description="개월 수(0~216, 만 18세 상한)", examples=[14])]
    gender: ChildGender
    temperament_memo: Annotated[str | None, Field(None, max_length=500, description="기질 메모")]
    allergies: Annotated[str | None, Field(None, max_length=500, description="알레르기. 저장 시 암호화된다.")]
    conditions: Annotated[str | None, Field(None, max_length=500, description="지병. 저장 시 암호화된다.")]
    medications: Annotated[str | None, Field(None, max_length=500, description="상시 투약. 저장 시 암호화된다.")]


class ChildResponse(BaseModel):
    """목록/일반 조회 응답 - 민감정보는 담지 않는다(REQ-NF-SEC-01)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    months_old: int
    gender: ChildGender
    temperament_memo: str | None
    has_sensitive_info: bool
    created_at: datetime


class ChildDetailResponse(ChildResponse):
    """본인(보호자) 조회 전용 - 매칭 하드필터 확인 등에 필요한 민감정보를 포함한다."""

    allergies: str | None
    conditions: str | None
    medications: str | None
