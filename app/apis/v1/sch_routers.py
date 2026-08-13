"""SCH 도메인 - 근무표(REQ-F-SCH-01/03/06)."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies import get_current_user
from app.dtos.work_schedule_dto import ShiftRegisterRequest, WorkScheduleResponse
from app.services.work_schedule_service import WorkScheduleService
from auth_kit.models import User

sch_router = APIRouter(prefix="/sch", tags=["sch"])

Session = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@sch_router.put(
    "/schedule",
    response_model=list[WorkScheduleResponse],
    summary="근무 템플릿 등록(당일, NIGHT는 익일에도 영향)",
    description="REQ-F-SCH-01/03/06. NIGHT(23:00-07:00)는 당일 46-47번 슬롯과 익일 0-13번 슬롯을 함께 마스킹한다.",
)
async def register_shift(
    session: Session, user: CurrentUser, request: ShiftRegisterRequest
) -> list[WorkScheduleResponse]:
    rows = await WorkScheduleService(session).register_shift(user, request.work_date, request.template)
    return [WorkScheduleResponse.model_validate(r) for r in rows]


@sch_router.get(
    "/schedule",
    response_model=list[WorkScheduleResponse],
    summary="기간별 근무표 조회",
)
async def list_schedule(
    session: Session, user: CurrentUser, start: date, end: date | None = None
) -> list[WorkScheduleResponse]:
    rows = await WorkScheduleService(session).list_range(user, start, end or start + timedelta(days=30))
    return [WorkScheduleResponse.model_validate(r) for r in rows]
