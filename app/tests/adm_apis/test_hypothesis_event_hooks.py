"""REQ-F-ADM-04: MAT 후보 노출, CAR 요청/수락/거절/완료, TRS 신뢰등급 전이 지점에서
`hypothesis_events`가 올바른 event_type/actor/target으로 적재되는지 검증."""

from datetime import date

import h3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
from app.models.children import ChildGender
from app.models.guardian_profile import HouseholdComposition, JobCategory, WorkType
from app.models.hypothesis_event import HypothesisEvent, HypothesisEventType
from app.models.trust_level import TrustLevel
from app.services.care_session_service import CareSessionService
from app.services.child_service import ChildService
from app.services.guardian_profile_service import GuardianProfileService
from app.services.matching_service import MatchingService
from app.services.parenting_values_service import ParentingValuesService
from app.services.trust_evaluation_service import TrustEvaluationService
from app.services.trust_level_service import TrustLevelService
from app.services.work_schedule_service import WorkScheduleService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES, TermsType

SEOUL_H3 = h3.latlng_to_cell(37.5665, 126.9780, 9)
NEARBY_H3 = h3.latlng_to_cell(37.5665, 126.9830, 9)  # 서울시청 기준 약 440m
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


async def _guardian_pair(session):
    """서로 후보로 노출될 만큼 가깝고 가치관이 유사한 두 사용자를 만든다."""
    a = await _signed_up_user(session, email="adm_a@example.com", nickname="ADM보호자A", phone="010-9301-0001")
    b = await _signed_up_user(session, email="adm_b@example.com", nickname="ADM보호자B", phone="010-9301-0002")

    for user, h3_cell, shift in ((a, SEOUL_H3, ShiftTemplate.DAY), (b, NEARBY_H3, ShiftTemplate.OFF)):
        await GuardianProfileService(session).upsert_profile(
            user,
            residence_h3=h3_cell,
            household_composition=HouseholdComposition.TWO_PARENT,
            job_category=JobCategory.IT,
            work_type=WorkType.SHIFT,
            tags=["FIRST_AID_CERTIFIED", "NON_SMOKING_HOUSEHOLD"],
        )
        await ParentingValuesService(session).submit_questionnaire(user, HIGH_WARMTH_HIGH_CONTROL)
        await WorkScheduleService(session).register_shift(user, FOR_DATE, shift)
        await ChildService(session).create_child(
            user,
            months_old=12,
            gender=ChildGender.MALE,
            temperament_memo=None,
            allergies=None,
            conditions=None,
            medications=None,
        )
    return a, b


async def _events(session, event_type: HypothesisEventType) -> list[HypothesisEvent]:
    result = await session.execute(select(HypothesisEvent).where(HypothesisEvent.event_type == event_type))
    return list(result.scalars().all())


async def test_candidate_exposure_logged_on_find_candidates():
    session = await _session()
    a, b = await _guardian_pair(session)

    await MatchingService(session).find_candidates(a, FOR_DATE)

    events = await _events(session, HypothesisEventType.CANDIDATE_EXPOSURE)
    assert any(e.actor_user_id == a.id and e.target_user_id == b.id for e in events)


async def test_request_accept_reject_and_completion_logged():
    session = await _session()
    a, b = await _guardian_pair(session)
    child_a = (await ChildService(session).list_children(a))[0]

    care_session = await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 14, 20)

    created = await _events(session, HypothesisEventType.REQUEST_CREATED)
    assert any(e.actor_user_id == a.id and e.target_user_id == b.id for e in created)

    await CareSessionService(session).accept(care_session.id, b)
    accepted = await _events(session, HypothesisEventType.REQUEST_ACCEPTED)
    assert any(e.actor_user_id == b.id and e.target_user_id == a.id for e in accepted)

    confirmed = await CareSessionService(session).checkin(care_session.id, b, *h3.cell_to_latlng(SEOUL_H3), None)
    completed = await CareSessionService(session).checkout(confirmed.id, b)
    session_completed = await _events(session, HypothesisEventType.SESSION_COMPLETED)
    assert any(
        e.actor_user_id == b.id and e.payload and e.payload["actual_minutes"] == completed.actual_minutes
        for e in session_completed
    )


async def test_reject_logged():
    session = await _session()
    a, b = await _guardian_pair(session)
    child_a = (await ChildService(session).list_children(a))[0]

    care_session = await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 14, 20)
    await CareSessionService(session).reject(care_session.id, b)

    rejected = await _events(session, HypothesisEventType.REQUEST_REJECTED)
    assert any(e.actor_user_id == b.id and e.target_user_id == a.id for e in rejected)


async def test_rematch_requested_logged_after_completed_pairing():
    session = await _session()
    a, b = await _guardian_pair(session)
    child_a = (await ChildService(session).list_children(a))[0]

    first = await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 14, 20)
    await CareSessionService(session).accept(first.id, b)
    checked_in = await CareSessionService(session).checkin(first.id, b, *h3.cell_to_latlng(SEOUL_H3), None)
    completed = await CareSessionService(session).checkout(checked_in.id, b)
    await TrustEvaluationService(session).submit(completed.id, a, rating=5, tags=[])
    await TrustEvaluationService(session).submit(completed.id, b, rating=5, tags=[])

    await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 20, 24)

    rematch = await _events(session, HypothesisEventType.REMATCH_REQUESTED)
    assert any(e.actor_user_id == a.id and e.target_user_id == b.id for e in rematch)


async def test_trust_level_transitions_logged_l1_l2_l3_and_demote():
    session = await _session()
    a, b = await _guardian_pair(session)
    child_a = (await ChildService(session).list_children(a))[0]

    care_session = await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 14, 20)
    await CareSessionService(session).accept(care_session.id, b)

    transitions = await _events(session, HypothesisEventType.TRUST_LEVEL_TRANSITION)
    assert any(e.payload and e.payload["new_level"] == TrustLevel.L1.value for e in transitions)

    service = TrustLevelService(session)
    await service.set_required_count(a, 1)
    await service.set_required_count(b, 1)
    joint = await service.schedule_joint_session(a, b.id, "공원", date(2026, 8, 20))

    transitions = await _events(session, HypothesisEventType.TRUST_LEVEL_TRANSITION)
    assert any(e.payload and e.payload["new_level"] == TrustLevel.L2.value for e in transitions)

    await service.confirm_joint_session(joint.id, a)
    await service.confirm_joint_session(joint.id, b)

    transitions = await _events(session, HypothesisEventType.TRUST_LEVEL_TRANSITION)
    assert any(e.payload and e.payload["new_level"] == TrustLevel.L3.value for e in transitions)

    admin = await _signed_up_user(session, email="adm_admin@example.com", nickname="ADM관리자", phone="010-9301-0003")
    admin.is_admin = True
    await session.commit()
    await session.refresh(admin)

    await service.demote(admin, a.id, b.id, "테스트 강등")
    transitions = await _events(session, HypothesisEventType.TRUST_LEVEL_TRANSITION)
    assert any(
        e.payload and e.payload.get("reason") == "테스트 강등" and e.payload["new_level"] == TrustLevel.L2.value
        for e in transitions
    )
