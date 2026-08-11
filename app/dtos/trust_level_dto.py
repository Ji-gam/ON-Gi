from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.joint_care_session import JointCareSessionStatus
from app.models.trust_level import TrustLevel


class TrustRelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_a_id: int
    user_b_id: int
    level: TrustLevel
    joint_session_count: int
    updated_at: datetime


class JointCareSessionCreate(BaseModel):
    partner_id: int
    place: str = Field(min_length=1, max_length=100)
    scheduled_date: date


class JointCareSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    initiator_id: int
    partner_id: int
    place: str
    scheduled_date: date
    confirmed_by_initiator: bool
    confirmed_by_partner: bool
    status: JointCareSessionStatus


class RequiredJointCountUpdate(BaseModel):
    required_joint_count: int = Field(ge=1)


class TrustSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    required_joint_count: int


class DemoteRequest(BaseModel):
    user_a_id: int
    user_b_id: int
    reason: str = Field(min_length=1, max_length=200)
