from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.care_session import CareSessionStatus


class CareRequestCreate(BaseModel):
    provider_id: int
    care_date: date
    start_slot: int = Field(ge=0, lt=48, description="시작 슬롯(0~47, 30분 단위)")
    end_slot: int = Field(gt=0, le=48, description="종료 슬롯(1~48, exclusive)")


class CareSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requester_id: int
    provider_id: int
    care_date: date
    start_slot: int
    end_slot: int
    status: CareSessionStatus
