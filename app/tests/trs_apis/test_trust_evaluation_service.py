"""REQ-F-TRS-05: 평가는 체크아웃 완료된 세션의 참여자만, 세션당 1회만 제출할 수 있다.
평가 미제출 상태에서는 새 요청 생성/수락이 차단된다."""

from datetime import date

import h3
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
from app.models.children import ChildGender
from app.services.care_session_service import CareSessionService
from app.services.child_service import ChildService
from app.services.trust_evaluation_service import TrustEvaluationService
from app.services.work_schedule_service import WorkScheduleService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES, TermsType

CARE_DATE = date(2026, 8, 12)
MEETING_H3 = h3.latlng_to_cell(37.5665, 126.9780, 9)
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


async def _confirmed_session(session, requester, provider):
    child = await ChildService(session).create_child(
        requester,
        months_old=12,
        gender=ChildGender.MALE,
        temperament_memo=None,
        allergies=None,
        conditions=None,
        medications=None,
    )
    await WorkScheduleService(session).register_shift(requester, CARE_DATE, ShiftTemplate.DAY)
    care_session = await CareSessionService(session).create_request(
        requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
    )
    return await CareSessionService(session).accept(care_session.id, provider)


async def _completed_session(session, requester, provider):
    confirmed = await _confirmed_session(session, requester, provider)
    await CareSessionService(session).checkin(confirmed.id, provider, MEETING_LAT, MEETING_LNG, None)
    return await CareSessionService(session).checkout(confirmed.id, provider)


async def test_submit_rejects_evaluation_before_checkout():
    session = await _session()
    requester = await _signed_up_user(session, email="t_req1@example.com", nickname="TRS요청자1", phone="010-9001-0001")
    provider = await _signed_up_user(session, email="t_prov1@example.com", nickname="TRS제공자1", phone="010-9001-0002")
    confirmed = await _confirmed_session(session, requester, provider)

    with pytest.raises(HTTPException) as exc:
        await TrustEvaluationService(session).submit(confirmed.id, requester, 5, ["시간 준수"])
    assert exc.value.status_code == 409


async def test_submit_succeeds_after_checkout_and_rejects_duplicate():
    session = await _session()
    requester = await _signed_up_user(session, email="t_req2@example.com", nickname="TRS요청자2", phone="010-9002-0001")
    provider = await _signed_up_user(session, email="t_prov2@example.com", nickname="TRS제공자2", phone="010-9002-0002")
    completed = await _completed_session(session, requester, provider)

    evaluation = await TrustEvaluationService(session).submit(completed.id, requester, 5, ["시간 준수", "소통 원활"])
    assert evaluation.evaluatee_id == provider.id
    assert evaluation.rating == 5

    with pytest.raises(HTTPException) as exc:
        await TrustEvaluationService(session).submit(completed.id, requester, 4, [])
    assert exc.value.status_code == 409


async def test_submit_rejects_non_participant():
    session = await _session()
    requester = await _signed_up_user(session, email="t_req3@example.com", nickname="TRS요청자3", phone="010-9003-0001")
    provider = await _signed_up_user(session, email="t_prov3@example.com", nickname="TRS제공자3", phone="010-9003-0002")
    stranger = await _signed_up_user(session, email="t_str3@example.com", nickname="TRS타인3", phone="010-9003-0003")
    completed = await _completed_session(session, requester, provider)

    with pytest.raises(HTTPException) as exc:
        await TrustEvaluationService(session).submit(completed.id, stranger, 5, [])
    assert exc.value.status_code == 404


async def test_pending_evaluation_blocks_new_request_and_accept():
    session = await _session()
    requester = await _signed_up_user(session, email="t_req4@example.com", nickname="TRS요청자4", phone="010-9004-0001")
    provider = await _signed_up_user(session, email="t_prov4@example.com", nickname="TRS제공자4", phone="010-9004-0002")
    completed = await _completed_session(session, requester, provider)

    child = await ChildService(session).create_child(
        requester,
        months_old=12,
        gender=ChildGender.MALE,
        temperament_memo=None,
        allergies=None,
        conditions=None,
        medications=None,
    )
    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).create_request(
            requester, provider.id, child.id, MEETING_H3, CARE_DATE, 20, 26
        )
    assert exc.value.status_code == 400

    await TrustEvaluationService(session).submit(completed.id, requester, 5, [])
    new_request = await CareSessionService(session).create_request(
        requester, provider.id, child.id, MEETING_H3, CARE_DATE, 20, 26
    )
    assert new_request.id != completed.id

    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).accept(new_request.id, provider)
    assert exc.value.status_code == 400

    await TrustEvaluationService(session).submit(completed.id, provider, 4, [])
    accepted = await CareSessionService(session).accept(new_request.id, provider)
    assert accepted.id == new_request.id
