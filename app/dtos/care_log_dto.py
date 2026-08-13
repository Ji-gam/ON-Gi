from pydantic import BaseModel, ConfigDict, Field


class CareLogUpsert(BaseModel):
    meal: str | None = Field(default=None, description="식사")
    sleep: str | None = Field(default=None, description="수면")
    mood: str | None = Field(default=None, description="기분")
    note: str | None = Field(default=None, description="특이사항")
    allergy_note: str | None = Field(default=None, description="알레르기 관련 항목(등록 아동은 필수)")


class CareLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    meal: str | None
    sleep: str | None
    mood: str | None
    note: str | None
    allergy_note: str | None
