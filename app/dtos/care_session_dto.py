from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.care_session import CareSessionStatus


class CareRequestCreate(BaseModel):
    provider_id: int
    child_id: int = Field(description="대상 아동(본인 소유 아동만 가능)")
    meeting_h3: str = Field(description="약속 장소 H3 셀(해상도 9)")
    care_date: date
    start_slot: int = Field(ge=0, lt=48, description="시작 슬롯(0~47, 30분 단위)")
    end_slot: int = Field(gt=0, le=48, description="종료 슬롯(1~48, exclusive)")


class CheckinRequest(BaseModel):
    lat: float = Field(description="체크인 시점 GPS 위도(저장은 계산된 거리만, 원본은 저장하지 않음)")
    lng: float = Field(description="체크인 시점 GPS 경도")
    reason: str | None = Field(default=None, description="반경 밖 체크인 사유(반경 밖일 때 필수)")


class CareSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requester_id: int
    provider_id: int
    child_id: int
    meeting_h3: str
    care_date: date
    start_slot: int
    end_slot: int
    status: CareSessionStatus
    checkin_at: datetime | None
    checkin_distance_m: float | None = Field(default=None, description="약속 장소 중심과의 거리(m)")
    checkin_out_of_range: bool
    checkin_reason: str | None
    checkout_at: datetime | None
    actual_minutes: int | None = Field(default=None, description="체크인·체크아웃 차이(분), 포인트 정산 근거")
