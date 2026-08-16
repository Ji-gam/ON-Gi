"""REQ-F-MAT-01/02/03/05/12: 매칭 후보는 거리 1km·완화불가 태그 하드필터를 통과해야 하고,
가치관 유사도·상보 스코어가 개별 수치로 노출되며 총점 내림차순으로 정렬되어야 한다."""

from datetime import date

import h3
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
from app.models.children import ChildGender
from app.models.guardian_profile import HouseholdComposition, JobCategory, WorkType
from app.services.child_service import ChildService
from app.services.guardian_profile_service import GuardianProfileService
from app.services.matching_service import MatchingService
from app.services.parenting_values_service import ParentingValuesService
from app.services.work_schedule_service import WorkScheduleService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES, TermsType

SEOUL_H3 = h3.latlng_to_cell(37.5665, 126.9780, 9)
NEARBY_H3 = h3.latlng_to_cell(37.5665, 126.9830, 9)  # 서울시청 기준 약 440m
FAR_H3 = h3.latlng_to_cell(37.5865, 126.9780, 9)  # 서울시청 기준 약 2.2km
FOR_DATE = date(2026, 8, 12)
HIGH_WARMTH_HIGH_CONTROL = [5, 5, 5, 5, 5, 5, 5, 5]


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)()


def _agreements() -> list[TermAgreementItem]:
    items = [TermAgreementItem(terms_type=t, version=CATALOG_BY_TYPE[t].version, agreed=True) for t in REQUIRED_TYPES]
    items.append(
        TermAgreementItem(
            terms_type=str(TermsType.GUARDIAN_CONSENT),
            version=CATALOG_BY_TYPE[str(TermsType.GUARDIAN_CONSENT)].version,
            agreed=True,
        )
    )
    return items


async def _signed_up_user(session, *, email: str, nickname: str, phone: str):
    result = await AuthService(session).signup(
        SignUpRequest(
            email=email,
            password="Password123!",
            name="홍길동",
            nickname=nickname,
            birth_date=date(1990, 1, 1),
            gender=Gender.MALE,
            phone_number=phone,
            agreements=_agreements(),
        )
    )
    return result.user


async def _setup_guardian(session, user, *, residence_h3: str, tags: list[str]):
    await GuardianProfileService(session).upsert_profile(
        user,
        residence_h3=residence_h3,
        job_category=JobCategory.IT,
        work_type=WorkType.SHIFT,
        household_composition=HouseholdComposition.TWO_PARENT,
        tags=tags,
    )


async def _setup_values(session, user, answers: list[int]):
    await ParentingValuesService(session).submit_questionnaire(user, answers)


async def _setup_child(session, user, *, months_old: int = 12, allergies: str | None = None):
    return await ChildService(session).create_child(
        user,
        months_old=months_old,
        gender=ChildGender.MALE,
        temperament_memo=None,
        allergies=allergies,
        conditions=None,
        medications=None,
    )


async def _setup_shift(session, user, template: ShiftTemplate):
    await WorkScheduleService(session).register_shift(user, FOR_DATE, template)


async def test_missing_guardian_profile_raises_400():
    session = await _session()
    user = await _signed_up_user(session, email="a@example.com", nickname="본인1", phone="010-1111-1111")

    with pytest.raises(HTTPException) as exc:
        await MatchingService(session).find_candidates(user, FOR_DATE)
    assert exc.value.status_code == 400


async def test_distance_hard_filter_excludes_beyond_1km():
    session = await _session()
    me = await _signed_up_user(session, email="me@example.com", nickname="본인2", phone="010-2222-2222")
    near = await _signed_up_user(session, email="near@example.com", nickname="이웃", phone="010-2222-3333")
    far = await _signed_up_user(session, email="far@example.com", nickname="먼동네", phone="010-2222-4444")

    tags = ["FIRST_AID_CERTIFIED", "NON_SMOKING_HOUSEHOLD"]
    await _setup_guardian(session, me, residence_h3=SEOUL_H3, tags=tags)
    await _setup_guardian(session, near, residence_h3=NEARBY_H3, tags=tags)
    await _setup_guardian(session, far, residence_h3=FAR_H3, tags=tags)
    for u in (me, near, far):
        await _setup_values(session, u, HIGH_WARMTH_HIGH_CONTROL)

    results = await MatchingService(session).find_candidates(me, FOR_DATE)
    result_ids = {c.user_id for c in results}
    assert near.id in result_ids
    assert far.id not in result_ids


async def test_mandatory_tag_filter_excludes_candidate_missing_allergy_response():
    session = await _session()
    me = await _signed_up_user(session, email="me2@example.com", nickname="본인3", phone="010-3333-1111")
    candidate = await _signed_up_user(session, email="cand@example.com", nickname="후보", phone="010-3333-2222")

    await _setup_guardian(session, me, residence_h3=SEOUL_H3, tags=["FIRST_AID_CERTIFIED", "NON_SMOKING_HOUSEHOLD"])
    await _setup_child(session, me, allergies="땅콩")
    await _setup_guardian(
        session, candidate, residence_h3=NEARBY_H3, tags=["FIRST_AID_CERTIFIED", "NON_SMOKING_HOUSEHOLD"]
    )
    await _setup_values(session, me, HIGH_WARMTH_HIGH_CONTROL)
    await _setup_values(session, candidate, HIGH_WARMTH_HIGH_CONTROL)

    excluded = await MatchingService(session).find_candidates(me, FOR_DATE)
    assert candidate.id not in {c.user_id for c in excluded}

    await _setup_guardian(
        session,
        candidate,
        residence_h3=NEARBY_H3,
        tags=["FIRST_AID_CERTIFIED", "NON_SMOKING_HOUSEHOLD", "ALLERGY_RESPONSE"],
    )
    included = await MatchingService(session).find_candidates(me, FOR_DATE)
    assert candidate.id in {c.user_id for c in included}


async def test_candidates_sorted_desc_and_expose_values_and_complementary_separately():
    session = await _session()
    me = await _signed_up_user(session, email="me3@example.com", nickname="본인4", phone="010-4444-1111")
    close_values = await _signed_up_user(
        session, email="cv@example.com", nickname="가치관가까움", phone="010-4444-2222"
    )
    far_values = await _signed_up_user(session, email="fv@example.com", nickname="가치관멀음", phone="010-4444-3333")

    tags = ["FIRST_AID_CERTIFIED", "NON_SMOKING_HOUSEHOLD"]
    await _setup_guardian(session, me, residence_h3=SEOUL_H3, tags=tags)
    await _setup_guardian(session, close_values, residence_h3=NEARBY_H3, tags=tags)
    await _setup_guardian(session, far_values, residence_h3=NEARBY_H3, tags=tags)

    await _setup_values(session, me, HIGH_WARMTH_HIGH_CONTROL)
    await _setup_values(session, close_values, HIGH_WARMTH_HIGH_CONTROL)
    await _setup_values(session, far_values, [1, 1, 1, 1, 1, 1, 1, 1])

    await _setup_shift(session, me, ShiftTemplate.DAY)
    await _setup_shift(session, close_values, ShiftTemplate.EVENING)
    await _setup_shift(session, far_values, ShiftTemplate.EVENING)

    results = await MatchingService(session).find_candidates(me, FOR_DATE)
    assert [c.total_score for c in results] == sorted((c.total_score for c in results), reverse=True)

    by_id = {c.user_id: c for c in results}
    assert by_id[close_values.id].values_similarity > by_id[far_values.id].values_similarity
    assert by_id[close_values.id].complementary_score == by_id[far_values.id].complementary_score
    assert by_id[close_values.id].total_score > by_id[far_values.id].total_score
    assert by_id[close_values.id].reason.endswith(".")
    assert "양육관이 가깝다" in by_id[close_values.id].reason
    assert "양육관이 가깝다" not in by_id[far_values.id].reason
