"""REQ-F-PNT-01/02/03/04: 복식부기 원장, 돌봄 정산(30분=1슬롯), 잔액·내역 조회, 시드/한도."""

from datetime import UTC, date, datetime, timedelta

import h3
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
from app.models.children import ChildGender
from app.models.point_account import NEGATIVE_BALANCE_LIMIT, SEED_POINTS
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


async def _completed_session_with_duration(session, requester, provider, *, minutes: int):
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
    confirmed = await CareSessionService(session).accept(care_session.id, provider)
    checked_in = await CareSessionService(session).checkin(confirmed.id, provider, MEETING_LAT, MEETING_LNG, None)

    checked_in.checkin_at = datetime.now(UTC) - timedelta(minutes=minutes)
    await session.commit()

    return await CareSessionService(session).checkout(checked_in.id, provider)


async def test_first_balance_query_grants_seed_points():
    session = await _session()
    user = await _signed_up_user(session, email="p1@example.com", nickname="포인트1", phone="010-9301-0001")

    balance = await PointLedgerService(session).get_balance(user.id)
    assert balance == SEED_POINTS


async def test_two_hour_care_completion_moves_four_slots():
    session = await _session()
    requester = await _signed_up_user(
        session, email="p2_req@example.com", nickname="포인트요청자2", phone="010-9302-0001"
    )
    provider = await _signed_up_user(
        session, email="p2_prov@example.com", nickname="포인트제공자2", phone="010-9302-0002"
    )

    service = PointLedgerService(session)
    requester_before = await service.get_balance(requester.id)
    provider_before = await service.get_balance(provider.id)

    await _completed_session_with_duration(session, requester, provider, minutes=120)

    assert await service.get_balance(requester.id) == requester_before - 4
    assert await service.get_balance(provider.id) == provider_before + 4


async def test_settlement_below_one_slot_creates_no_transaction():
    session = await _session()
    requester = await _signed_up_user(
        session, email="p3_req@example.com", nickname="포인트요청자3", phone="010-9303-0001"
    )
    provider = await _signed_up_user(
        session, email="p3_prov@example.com", nickname="포인트제공자3", phone="010-9303-0002"
    )

    service = PointLedgerService(session)
    requester_before = await service.get_balance(requester.id)
    provider_before = await service.get_balance(provider.id)

    await _completed_session_with_duration(session, requester, provider, minutes=10)

    assert await service.get_balance(requester.id) == requester_before
    assert await service.get_balance(provider.id) == provider_before
    assert await service.list_transactions(requester.id) == []


async def test_ledger_sum_is_always_zero_across_many_transactions():
    session = await _session()
    requester = await _signed_up_user(
        session, email="p4_req@example.com", nickname="포인트요청자4", phone="010-9304-0001"
    )
    provider = await _signed_up_user(
        session, email="p4_prov@example.com", nickname="포인트제공자4", phone="010-9304-0002"
    )

    service = PointLedgerService(session)
    for _ in range(5):
        await service._transfer(payer_id=requester.id, payee_id=provider.id, amount=1, reason="테스트 거래")

    requester_entries = await service.list_transactions(requester.id)
    provider_entries = await service.list_transactions(provider.id)
    total = sum(entry.amount for entry, _ in requester_entries) + sum(entry.amount for entry, _ in provider_entries)
    assert total == 0
    assert len(requester_entries) == 5


async def test_transaction_history_returns_latest_first_with_counterparty_and_reason():
    session = await _session()
    requester = await _signed_up_user(
        session, email="p5_req@example.com", nickname="포인트요청자5", phone="010-9305-0001"
    )
    provider = await _signed_up_user(
        session, email="p5_prov@example.com", nickname="포인트제공자5", phone="010-9305-0002"
    )

    await _completed_session_with_duration(session, requester, provider, minutes=120)

    entries = await PointLedgerService(session).list_transactions(requester.id)
    entry, transaction = entries[0]
    assert entry.counterparty_id == provider.id
    assert entry.amount == -4
    assert transaction.reason == "돌봄 정산"


async def test_negative_balance_limit_blocks_new_request():
    session = await _session()
    requester = await _signed_up_user(
        session, email="p6_req@example.com", nickname="포인트요청자6", phone="010-9306-0001"
    )
    provider = await _signed_up_user(
        session, email="p6_prov@example.com", nickname="포인트제공자6", phone="010-9306-0002"
    )

    service = PointLedgerService(session)
    account = await service.account_repo.get_or_create(requester.id)
    account.balance = NEGATIVE_BALANCE_LIMIT
    await session.commit()

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

    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).create_request(
            requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
        )
    assert exc.value.status_code == 400
