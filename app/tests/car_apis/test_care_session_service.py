"""REQ-F-CAR-01/02/03/05: 돌봄 요청은 상보 가능 구간(제공자 가용+요청자 불가)만 생성 가능하고,
수락/거절로 CONFIRMED/REJECTED로 전이되며, 제공자가 아니거나 이미 처리된 요청은 거부된다.
체크인은 약속 장소 반경 밖이면 사유가 필요하고, 체크아웃은 체크인 이후에만 가능하다."""

from datetime import date

import h3
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
from app.models.care_session import CareSessionStatus
from app.models.children import ChildGender
from app.services.care_session_service import CareSessionService
from app.services.child_service import ChildService
from app.services.work_schedule_service import WorkScheduleService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES, TermsType

CARE_DATE = date(2026, 8, 12)
MEETING_H3 = h3.latlng_to_cell(37.5665, 126.9780, 9)  # 서울시청
MEETING_LAT, MEETING_LNG = h3.cell_to_latlng(MEETING_H3)


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


async def _setup_child(session, user, *, allergies: str | None = None):
    return await ChildService(session).create_child(
        user,
        months_old=12,
        gender=ChildGender.MALE,
        temperament_memo=None,
        allergies=allergies,
        conditions=None,
        medications=None,
    )


async def _create_confirmed_session(session, requester, provider, child):
    await WorkScheduleService(session).register_shift(requester, CARE_DATE, ShiftTemplate.DAY)
    care_session = await CareSessionService(session).create_request(
        requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
    )
    return await CareSessionService(session).accept(care_session.id, provider)


async def test_create_request_rejects_non_complementary_range():
    session = await _session()
    requester = await _signed_up_user(session, email="req@example.com", nickname="요청자", phone="010-1111-1111")
    provider = await _signed_up_user(session, email="prov@example.com", nickname="제공자", phone="010-1111-2222")
    child = await _setup_child(session, requester)

    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).create_request(
            requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
        )
    assert exc.value.status_code == 400


async def test_create_request_rejects_child_not_owned_by_requester():
    session = await _session()
    requester = await _signed_up_user(session, email="req1b@example.com", nickname="요청자1b", phone="010-1111-9999")
    provider = await _signed_up_user(session, email="prov1b@example.com", nickname="제공자1b", phone="010-1111-8888")
    stranger = await _signed_up_user(session, email="str1b@example.com", nickname="타인1b", phone="010-1111-7777")
    others_child = await _setup_child(session, stranger)

    await WorkScheduleService(session).register_shift(requester, CARE_DATE, ShiftTemplate.DAY)
    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).create_request(
            requester, provider.id, others_child.id, MEETING_H3, CARE_DATE, 14, 20
        )
    assert exc.value.status_code == 400


async def test_create_request_succeeds_when_complementary():
    session = await _session()
    requester = await _signed_up_user(session, email="req2@example.com", nickname="요청자2", phone="010-2222-1111")
    provider = await _signed_up_user(session, email="prov2@example.com", nickname="제공자2", phone="010-2222-2222")
    child = await _setup_child(session, requester)

    await WorkScheduleService(session).register_shift(requester, CARE_DATE, ShiftTemplate.DAY)
    care_session = await CareSessionService(session).create_request(
        requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
    )
    assert care_session.status == CareSessionStatus.REQUESTED
    assert care_session.child_id == child.id
    assert care_session.start_slot == 14
    assert care_session.end_slot == 20


async def test_accept_transitions_to_confirmed_and_only_provider_can_accept():
    session = await _session()
    requester = await _signed_up_user(session, email="req3@example.com", nickname="요청자3", phone="010-3333-1111")
    provider = await _signed_up_user(session, email="prov3@example.com", nickname="제공자3", phone="010-3333-2222")
    stranger = await _signed_up_user(session, email="str3@example.com", nickname="타인3", phone="010-3333-3333")
    child = await _setup_child(session, requester)

    await WorkScheduleService(session).register_shift(requester, CARE_DATE, ShiftTemplate.DAY)
    care_session = await CareSessionService(session).create_request(
        requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
    )

    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).accept(care_session.id, stranger)
    assert exc.value.status_code == 404

    accepted = await CareSessionService(session).accept(care_session.id, provider)
    assert accepted.status == CareSessionStatus.CONFIRMED

    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).accept(care_session.id, provider)
    assert exc.value.status_code == 409


async def test_reject_transitions_to_rejected_and_allows_reapply():
    session = await _session()
    requester = await _signed_up_user(session, email="req4@example.com", nickname="요청자4", phone="010-4444-1111")
    provider = await _signed_up_user(session, email="prov4@example.com", nickname="제공자4", phone="010-4444-2222")
    child = await _setup_child(session, requester)

    await WorkScheduleService(session).register_shift(requester, CARE_DATE, ShiftTemplate.DAY)
    care_session = await CareSessionService(session).create_request(
        requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
    )

    rejected = await CareSessionService(session).reject(care_session.id, provider)
    assert rejected.status == CareSessionStatus.REJECTED

    reapplied = await CareSessionService(session).create_request(
        requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
    )
    assert reapplied.id != care_session.id
    assert reapplied.status == CareSessionStatus.REQUESTED


async def test_checkin_within_radius_succeeds_without_reason():
    session = await _session()
    requester = await _signed_up_user(session, email="req5@example.com", nickname="요청자5", phone="010-5555-1111")
    provider = await _signed_up_user(session, email="prov5@example.com", nickname="제공자5", phone="010-5555-2222")
    child = await _setup_child(session, requester)
    confirmed = await _create_confirmed_session(session, requester, provider, child)

    checked_in = await CareSessionService(session).checkin(confirmed.id, provider, MEETING_LAT, MEETING_LNG, None)
    assert checked_in.checkin_at is not None
    assert checked_in.checkin_out_of_range is False


async def test_checkin_outside_radius_requires_reason():
    session = await _session()
    requester = await _signed_up_user(session, email="req6@example.com", nickname="요청자6", phone="010-6666-1111")
    provider = await _signed_up_user(session, email="prov6@example.com", nickname="제공자6", phone="010-6666-2222")
    child = await _setup_child(session, requester)
    confirmed = await _create_confirmed_session(session, requester, provider, child)

    far_lat, far_lng = 37.6, 127.1  # 서울시청에서 약 10km+ 이상
    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).checkin(confirmed.id, provider, far_lat, far_lng, None)
    assert exc.value.status_code == 400

    checked_in = await CareSessionService(session).checkin(
        confirmed.id, provider, far_lat, far_lng, "차가 막혀 근처에서 체크인"
    )
    assert checked_in.checkin_out_of_range is True
    assert checked_in.checkin_reason == "차가 막혀 근처에서 체크인"


async def test_checkout_requires_prior_checkin_and_computes_minutes():
    session = await _session()
    requester = await _signed_up_user(session, email="req7@example.com", nickname="요청자7", phone="010-7777-1111")
    provider = await _signed_up_user(session, email="prov7@example.com", nickname="제공자7", phone="010-7777-2222")
    child = await _setup_child(session, requester)
    confirmed = await _create_confirmed_session(session, requester, provider, child)

    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).checkout(confirmed.id, provider)
    assert exc.value.status_code == 409

    await CareSessionService(session).checkin(confirmed.id, provider, MEETING_LAT, MEETING_LNG, None)
    checked_out = await CareSessionService(session).checkout(confirmed.id, provider)
    assert checked_out.checkout_at is not None
    assert checked_out.actual_minutes is not None
    assert checked_out.actual_minutes >= 0
