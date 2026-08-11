"""REQ-F-ACC-04: 보호자 프로필은 H3 인덱스(좌표 아님)로 거주지를 저장하고, 태그는 알려진
코드 목록만 허용하며, 재등록 시 upsert 되어야 한다."""

from datetime import date

import h3
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.guardian_profile import HouseholdComposition, JobCategory, WorkType
from app.services.guardian_profile_service import GuardianProfileService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES

SEOUL_H3 = h3.latlng_to_cell(37.5665, 126.9780, 9)


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)()


async def _signed_up_user(session, *, email: str, nickname: str, phone: str):
    agreements = [
        TermAgreementItem(terms_type=t, version=CATALOG_BY_TYPE[t].version, agreed=True) for t in REQUIRED_TYPES
    ]
    result = await AuthService(session).signup(
        SignUpRequest(
            email=email,
            password="Password123!",
            name="홍길동",
            nickname=nickname,
            birth_date=date(1990, 1, 1),
            gender=Gender.MALE,
            phone_number=phone,
            agreements=agreements,
        )
    )
    return result.user


async def test_invalid_h3_index_is_rejected():
    session = await _session()
    user = await _signed_up_user(session, email="a@example.com", nickname="보호자1", phone="010-1111-1111")

    with pytest.raises(HTTPException) as exc:
        await GuardianProfileService(session).upsert_profile(
            user,
            residence_h3="not-a-valid-h3",
            job_category=JobCategory.IT,
            work_type=WorkType.REMOTE,
            household_composition=HouseholdComposition.TWO_PARENT,
            tags=[],
        )
    assert exc.value.status_code == 400


async def test_unknown_tag_code_is_rejected():
    session = await _session()
    user = await _signed_up_user(session, email="b@example.com", nickname="보호자2", phone="010-2222-2222")

    with pytest.raises(HTTPException) as exc:
        await GuardianProfileService(session).upsert_profile(
            user,
            residence_h3=SEOUL_H3,
            job_category=JobCategory.IT,
            work_type=WorkType.REMOTE,
            household_composition=HouseholdComposition.TWO_PARENT,
            tags=["NOT_A_REAL_TAG"],
        )
    assert exc.value.status_code == 400


async def test_upsert_creates_then_updates_same_profile():
    session = await _session()
    user = await _signed_up_user(session, email="c@example.com", nickname="보호자3", phone="010-3333-3333")

    profile, tags = await GuardianProfileService(session).upsert_profile(
        user,
        residence_h3=SEOUL_H3,
        job_category=JobCategory.IT,
        work_type=WorkType.REMOTE,
        household_composition=HouseholdComposition.TWO_PARENT,
        tags=["HAS_VEHICLE"],
    )
    assert profile.residence_h3 == SEOUL_H3
    assert tags == ["HAS_VEHICLE"]

    profile2, tags2 = await GuardianProfileService(session).upsert_profile(
        user,
        residence_h3=SEOUL_H3,
        job_category=JobCategory.HEALTHCARE,
        work_type=WorkType.SHIFT,
        household_composition=HouseholdComposition.SINGLE_PARENT,
        tags=["FIRST_AID_CERTIFIED", "NON_SMOKING_HOUSEHOLD"],
    )
    assert profile2.user_id == profile.user_id
    assert profile2.job_category == JobCategory.HEALTHCARE
    assert tags2 == ["FIRST_AID_CERTIFIED", "NON_SMOKING_HOUSEHOLD"]

    fetched, fetched_tags = await GuardianProfileService(session).get_profile(user)
    assert fetched.work_type == WorkType.SHIFT
    assert fetched_tags == ["FIRST_AID_CERTIFIED", "NON_SMOKING_HOUSEHOLD"]


async def test_get_profile_without_registration_is_404():
    session = await _session()
    user = await _signed_up_user(session, email="d@example.com", nickname="보호자4", phone="010-4444-4444")

    with pytest.raises(HTTPException) as exc:
        await GuardianProfileService(session).get_profile(user)
    assert exc.value.status_code == 404
