"""REQ-F-PNT-05: 요청 확정 시 포인트 홀드, 완료 시 정산 전환(미사용분 반환 포함)."""

from datetime import UTC, date, datetime, timedelta

import h3
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
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


async def test_accept_holds_expected_slots_from_requester():
    session = await _session()
    requester = await _signed_up_user(
        session, email="h1_req@example.com", nickname="홀드요청자1", phone="010-9401-0001"
    )
    provider = await _signed_up_user(
        session, email="h1_prov@example.com", nickname="홀드제공자1", phone="010-9401-0002"
    )

    ledger = PointLedgerService(session)
    balance_before = await ledger.get_balance(requester.id)

    confirmed = await _confirmed_session(session, requester, provider)

    assert await ledger.get_balance(requester.id) == balance_before - 6
    assert await ledger.get_held_balance(requester.id) == 6
    hold = await ledger.hold_repo.get_by_care_session(confirmed.id)
    assert hold is not None
    assert hold.status == PointHoldStatus.HELD
    assert hold.amount == 6


async def test_checkout_settles_hold_and_releases_unused_portion():
    session = await _session()
    requester = await _signed_up_user(
        session, email="h2_req@example.com", nickname="홀드요청자2", phone="010-9402-0001"
    )
    provider = await _signed_up_user(
        session, email="h2_prov@example.com", nickname="홀드제공자2", phone="010-9402-0002"
    )

    ledger = PointLedgerService(session)
    requester_before = await ledger.get_balance(requester.id)
    provider_before = await ledger.get_balance(provider.id)

    confirmed = await _confirmed_session(session, requester, provider)
    checked_in = await CareSessionService(session).checkin(confirmed.id, provider, MEETING_LAT, MEETING_LNG, None)
    checked_in.checkin_at = datetime.now(UTC) - timedelta(minutes=120)
    await session.commit()
    await CareSessionService(session).checkout(checked_in.id, provider)

    assert await ledger.get_balance(requester.id) == requester_before - 4
    assert await ledger.get_balance(provider.id) == provider_before + 4
    assert await ledger.get_held_balance(requester.id) == 0

    hold = await ledger.hold_repo.get_by_care_session(confirmed.id)
    assert hold.status == PointHoldStatus.SETTLED


async def test_checkout_beyond_held_amount_is_clamped_to_hold():
    session = await _session()
    requester = await _signed_up_user(
        session, email="h3_req@example.com", nickname="홀드요청자3", phone="010-9403-0001"
    )
    provider = await _signed_up_user(
        session, email="h3_prov@example.com", nickname="홀드제공자3", phone="010-9403-0002"
    )

    ledger = PointLedgerService(session)
    requester_before = await ledger.get_balance(requester.id)
    provider_before = await ledger.get_balance(provider.id)

    confirmed = await _confirmed_session(session, requester, provider)  # 6슬롯 홀드
    checked_in = await CareSessionService(session).checkin(confirmed.id, provider, MEETING_LAT, MEETING_LNG, None)
    checked_in.checkin_at = datetime.now(UTC) - timedelta(minutes=300)  # 10슬롯 상당(홀드 초과)
    await session.commit()
    await CareSessionService(session).checkout(checked_in.id, provider)

    assert await ledger.get_balance(requester.id) == requester_before - 6
    assert await ledger.get_balance(provider.id) == provider_before + 6
    assert await ledger.get_held_balance(requester.id) == 0


async def test_checkout_below_one_slot_returns_entire_hold_with_no_transaction():
    session = await _session()
    requester = await _signed_up_user(
        session, email="h4_req@example.com", nickname="홀드요청자4", phone="010-9404-0001"
    )
    provider = await _signed_up_user(
        session, email="h4_prov@example.com", nickname="홀드제공자4", phone="010-9404-0002"
    )

    ledger = PointLedgerService(session)
    requester_before = await ledger.get_balance(requester.id)
    provider_before = await ledger.get_balance(provider.id)

    confirmed = await _confirmed_session(session, requester, provider)
    checked_in = await CareSessionService(session).checkin(confirmed.id, provider, MEETING_LAT, MEETING_LNG, None)
    checked_in.checkin_at = datetime.now(UTC) - timedelta(minutes=10)
    await session.commit()
    await CareSessionService(session).checkout(checked_in.id, provider)

    assert await ledger.get_balance(requester.id) == requester_before
    assert await ledger.get_balance(provider.id) == provider_before
    assert await ledger.get_held_balance(requester.id) == 0
    assert await ledger.list_transactions(requester.id) == []
