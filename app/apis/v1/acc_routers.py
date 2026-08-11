"""ACC 도메인 - 아동(Child) 등록/조회 (REQ-F-ACC-05/06)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import get_db
from app.dependencies import get_current_user
from app.dtos.children import ChildCreateRequest, ChildDetailResponse, ChildResponse
from app.dtos.guardian_profile_dto import GuardianProfileResponse, GuardianProfileUpsertRequest
from app.models.children import Child
from app.services.child_service import ChildService
from app.services.guardian_profile_service import GuardianProfileService
from auth_kit.models import User

acc_router = APIRouter(prefix="/acc", tags=["acc"])

Session = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _detail(child: Child) -> ChildDetailResponse:
    sensitive = child.sensitive
    return ChildDetailResponse(
        id=child.id,
        months_old=child.months_old,
        gender=child.gender,
        temperament_memo=child.temperament_memo,
        has_sensitive_info=child.has_sensitive_info,
        created_at=child.created_at,
        allergies=sensitive.allergies if sensitive else None,
        conditions=sensitive.conditions if sensitive else None,
        medications=sensitive.medications if sensitive else None,
    )


@acc_router.post(
    "/children",
    response_model=ChildDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="아동 등록",
    description="법정대리인 동의(GUARDIAN_CONSENT)를 먼저 제출해야 한다.",
    responses={status.HTTP_400_BAD_REQUEST: {"description": "법정대리인 동의 미완료"}},
)
async def create_child(session: Session, user: CurrentUser, request: ChildCreateRequest) -> ChildDetailResponse:
    child = await ChildService(session).create_child(
        user,
        months_old=request.months_old,
        gender=request.gender,
        temperament_memo=request.temperament_memo,
        allergies=request.allergies,
        conditions=request.conditions,
        medications=request.medications,
    )
    return _detail(child)


@acc_router.get("/children", response_model=list[ChildResponse], summary="내 아동 목록")
async def list_children(session: Session, user: CurrentUser) -> list[ChildResponse]:
    children = await ChildService(session).list_children(user)
    return [ChildResponse.model_validate(c) for c in children]


@acc_router.get(
    "/children/{child_id}",
    response_model=ChildDetailResponse,
    summary="아동 상세(민감정보 포함)",
    responses={status.HTTP_404_NOT_FOUND: {"description": "본인 소유가 아니거나 존재하지 않는 아동"}},
)
async def get_child(session: Session, user: CurrentUser, child_id: int) -> ChildDetailResponse:
    child = await ChildService(session).get_child(user, child_id)
    return _detail(child)


@acc_router.delete(
    "/children/{child_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="아동 삭제",
    responses={status.HTTP_404_NOT_FOUND: {"description": "본인 소유가 아니거나 존재하지 않는 아동"}},
)
async def delete_child(session: Session, user: CurrentUser, child_id: int) -> None:
    await ChildService(session).delete_child(user, child_id)


@acc_router.put(
    "/guardian-profile",
    response_model=GuardianProfileResponse,
    summary="보호자 프로필 등록/수정",
    description="거주지는 H3 인덱스 문자열로 전달한다(좌표 아님). REQ-F-ACC-04.",
    responses={status.HTTP_400_BAD_REQUEST: {"description": "H3 인덱스 형식이 유효하지 않거나 알 수 없는 태그"}},
)
async def upsert_guardian_profile(
    session: Session, user: CurrentUser, request: GuardianProfileUpsertRequest
) -> GuardianProfileResponse:
    profile, tags = await GuardianProfileService(session).upsert_profile(
        user,
        residence_h3=request.residence_h3,
        job_category=request.job_category,
        work_type=request.work_type,
        household_composition=request.household_composition,
        tags=request.tags,
    )
    return GuardianProfileResponse(
        residence_h3=profile.residence_h3,
        job_category=profile.job_category,
        work_type=profile.work_type,
        household_composition=profile.household_composition,
        tags=tags,
        updated_at=profile.updated_at,
    )


@acc_router.get(
    "/guardian-profile",
    response_model=GuardianProfileResponse,
    summary="내 보호자 프로필 조회",
    responses={status.HTTP_404_NOT_FOUND: {"description": "등록된 프로필 없음"}},
)
async def get_guardian_profile(session: Session, user: CurrentUser) -> GuardianProfileResponse:
    profile, tags = await GuardianProfileService(session).get_profile(user)
    return GuardianProfileResponse(
        residence_h3=profile.residence_h3,
        job_category=profile.job_category,
        work_type=profile.work_type,
        household_composition=profile.household_composition,
        tags=tags,
        updated_at=profile.updated_at,
    )
