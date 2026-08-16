"""REQ-F-CAR-07/PNT-05: 세션 취소·노쇼 처리 및 홀드 반환/몰수 방향."""

from datetime import date, timedelta

import h3
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
from app.models.care_session import CareSessionStatus
from app.models.children import ChildGender
from app.models.point_hold import PointHoldStatus
from app.services.care_session_service import CareSessionService
from app.services.child_service import ChildService
from app.services.point_ledger_service import PointLedgerService
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


async def _reschedule(session, care_session, care_date: date) -> None:
    """취소 마감 판정에 쓰이는 예정 시각만 바꾼다(상보 조건 재검증 없이 직접 필드 수정)."""
    care_session.care_date = care_date
    await session.commit()


FUTURE_DATE = date.today() + timedelta(days=3)  # 취소 마감(2시간 전)보다 한참 이전 - 페널티 없음
PAST_DATE = date.today() - timedelta(days=1)  # 취소 마감도, 세션 종료 시각도 이미 지난 상태


async def test_cancel_before_deadline_returns_hold_in_full_without_penalty():
    session = await _session()
    requester = await _signed_up_user(
        session, email="c1_req@example.com", nickname="취소요청자1", phone="010-9501-0001"
    )
    provider = await _signed_up_user(
        session, email="c1_prov@example.com", nickname="취소제공자1", phone="010-9501-0002"
    )

    ledger = PointLedgerService(session)
    requester_before = await ledger.get_balance(requester.id)

    confirmed = await _confirmed_session(session, requester, provider)
    await _reschedule(session, confirmed, FUTURE_DATE)

    cancelled = await CareSessionService(session).cancel(confirmed.id, requester, "일정 변경")
    assert cancelled.status == CareSessionStatus.CANCELLED
    assert cancelled.at_fault_user_id is None

    assert await ledger.get_balance(requester.id) == requester_before
    assert await ledger.get_held_balance(requester.id) == 0
    assert await ledger.list_transactions(requester.id) == []

    hold = await ledger.hold_repo.get_by_care_session(confirmed.id)
    assert hold.status == PointHoldStatus.RELEASED


async def test_requester_cancel_after_deadline_forfeits_hold_to_provider():
    session = await _session()
    requester = await _signed_up_user(
        session, email="c2_req@example.com", nickname="취소요청자2", phone="010-9502-0001"
    )
    provider = await _signed_up_user(
        session, email="c2_prov@example.com", nickname="취소제공자2", phone="010-9502-0002"
    )

    ledger = PointLedgerService(session)
    requester_before = await ledger.get_balance(requester.id)
    provider_before = await ledger.get_balance(provider.id)

    confirmed = await _confirmed_session(session, requester, provider)
    await _reschedule(session, confirmed, PAST_DATE)

    cancelled = await CareSessionService(session).cancel(confirmed.id, requester, "늦은 취소")
    assert cancelled.at_fault_user_id == requester.id

    assert await ledger.get_balance(requester.id) == requester_before - 6
    assert await ledger.get_balance(provider.id) == provider_before + 6
    assert await ledger.get_held_balance(requester.id) == 0

    entries = await ledger.list_transactions(requester.id)
    assert entries[0][1].reason == "취소 페널티"


async def test_provider_cancel_after_deadline_returns_hold_to_requester_without_penalty():
    session = await _session()
    requester = await _signed_up_user(
        session, email="c3_req@example.com", nickname="취소요청자3", phone="010-9503-0001"
    )
    provider = await _signed_up_user(
        session, email="c3_prov@example.com", nickname="취소제공자3", phone="010-9503-0002"
    )

    ledger = PointLedgerService(session)
    requester_before = await ledger.get_balance(requester.id)

    confirmed = await _confirmed_session(session, requester, provider)
    await _reschedule(session, confirmed, PAST_DATE)

    cancelled = await CareSessionService(session).cancel(confirmed.id, provider, "제공자 사정")
    assert cancelled.at_fault_user_id == provider.id

    assert await ledger.get_balance(requester.id) == requester_before
    assert await ledger.get_held_balance(requester.id) == 0
    assert await ledger.list_transactions(requester.id) == []


async def test_cannot_cancel_after_checkin():
    session = await _session()
    requester = await _signed_up_user(
        session, email="c4_req@example.com", nickname="취소요청자4", phone="010-9504-0001"
    )
    provider = await _signed_up_user(
        session, email="c4_prov@example.com", nickname="취소제공자4", phone="010-9504-0002"
    )

    confirmed = await _confirmed_session(session, requester, provider)
    await CareSessionService(session).checkin(confirmed.id, provider, MEETING_LAT, MEETING_LNG, None)

    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).cancel(confirmed.id, requester, "취소 시도")
    assert exc.value.status_code == 409


async def test_no_show_before_scheduled_end_is_rejected():
    session = await _session()
    requester = await _signed_up_user(
        session, email="c5_req@example.com", nickname="취소요청자5", phone="010-9505-0001"
    )
    provider = await _signed_up_user(
        session, email="c5_prov@example.com", nickname="취소제공자5", phone="010-9505-0002"
    )

    confirmed = await _confirmed_session(session, requester, provider)
    await _reschedule(session, confirmed, FUTURE_DATE)

    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).report_no_show(confirmed.id, requester, "안 옴")
    assert exc.value.status_code == 400


async def test_requester_reports_provider_no_show_returns_hold_in_full():
    session = await _session()
    requester = await _signed_up_user(
        session, email="c6_req@example.com", nickname="취소요청자6", phone="010-9506-0001"
    )
    provider = await _signed_up_user(
        session, email="c6_prov@example.com", nickname="취소제공자6", phone="010-9506-0002"
    )

    ledger = PointLedgerService(session)
    requester_before = await ledger.get_balance(requester.id)

    confirmed = await _confirmed_session(session, requester, provider)
    await _reschedule(session, confirmed, PAST_DATE)

    reported = await CareSessionService(session).report_no_show(confirmed.id, requester, "제공자가 나타나지 않음")
    assert reported.status == CareSessionStatus.NO_SHOW
    assert reported.at_fault_user_id == provider.id

    assert await ledger.get_balance(requester.id) == requester_before
    assert await ledger.get_held_balance(requester.id) == 0
    assert await ledger.list_transactions(requester.id) == []


async def test_provider_reports_requester_no_show_forfeits_hold():
    session = await _session()
    requester = await _signed_up_user(
        session, email="c7_req@example.com", nickname="취소요청자7", phone="010-9507-0001"
    )
    provider = await _signed_up_user(
        session, email="c7_prov@example.com", nickname="취소제공자7", phone="010-9507-0002"
    )

    ledger = PointLedgerService(session)
    requester_before = await ledger.get_balance(requester.id)
    provider_before = await ledger.get_balance(provider.id)

    confirmed = await _confirmed_session(session, requester, provider)
    await _reschedule(session, confirmed, PAST_DATE)

    reported = await CareSessionService(session).report_no_show(confirmed.id, provider, "요청자가 아이를 데려오지 않음")
    assert reported.status == CareSessionStatus.NO_SHOW
    assert reported.at_fault_user_id == requester.id

    assert await ledger.get_balance(requester.id) == requester_before - 6
    assert await ledger.get_balance(provider.id) == provider_before + 6

    entries = await ledger.list_transactions(requester.id)
    assert entries[0][1].reason == "노쇼 페널티"
