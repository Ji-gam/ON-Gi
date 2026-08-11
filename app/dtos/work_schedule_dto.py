from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.utils.schedule_slots import ShiftTemplate


class ShiftRegisterRequest(BaseModel):
    work_date: date
    template: ShiftTemplate


class WorkScheduleResponse(BaseModel):
    work_date: date
    slot_bitmask: int = Field(description="30분 단위 48비트 마스크. 1=가용, 0=근무 중(불가)")
    shift_template: ShiftTemplate
    updated_at: datetime

    model_config = {"from_attributes": True}
