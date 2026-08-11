"""REQ-F-CAR-01/02: 돌봄 요청은 상보 가능 구간(제공자 가용+요청자 불가)만 생성 가능하고,
수락/거절로 CONFIRMED/REJECTED로 전이되며, 제공자가 아니거나 이미 처리된 요청은 거부된다."""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
from app.models.care_session import CareSessionStatus
from app.services.care_session_service import CareSessionService
from app.services.work_schedule_service import WorkScheduleService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES, TermsType

CARE_DATE = date(2026, 8, 12)


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


async def test_create_request_rejects_non_complementary_range():
    session = await _session()
    requester = await _signed_up_user(session, email="req@example.com", nickname="요청자", phone="010-1111-1111")
    provider = await _signed_up_user(session, email="prov@example.com", nickname="제공자", phone="010-1111-2222")

    # 둘 다 근무표 미등록 -> 풀가용(요청자도 가용)이라 "요청자 불가" 조건을 만족하지 못함
    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).create_request(requester, provider.id, CARE_DATE, 14, 20)
    assert exc.value.status_code == 400


async def test_create_request_succeeds_when_complementary():
    session = await _session()
    requester = await _signed_up_user(session, email="req2@example.com", nickname="요청자2", phone="010-2222-1111")
    provider = await _signed_up_user(session, email="prov2@example.com", nickname="제공자2", phone="010-2222-2222")

    # 요청자는 DAY(14~29 불가), 제공자는 OFF(전부 가용) -> 14~20 구간은 상보 가능
    await WorkScheduleService(session).register_shift(requester, CARE_DATE, ShiftTemplate.DAY)

    care_session = await CareSessionService(session).create_request(requester, provider.id, CARE_DATE, 14, 20)
    assert care_session.status == CareSessionStatus.REQUESTED
    assert care_session.start_slot == 14
    assert care_session.end_slot == 20


async def test_accept_transitions_to_confirmed_and_only_provider_can_accept():
    session = await _session()
    requester = await _signed_up_user(session, email="req3@example.com", nickname="요청자3", phone="010-3333-1111")
    provider = await _signed_up_user(session, email="prov3@example.com", nickname="제공자3", phone="010-3333-2222")
    stranger = await _signed_up_user(session, email="str3@example.com", nickname="타인", phone="010-3333-3333")

    await WorkScheduleService(session).register_shift(requester, CARE_DATE, ShiftTemplate.DAY)
    care_session = await CareSessionService(session).create_request(requester, provider.id, CARE_DATE, 14, 20)

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

    await WorkScheduleService(session).register_shift(requester, CARE_DATE, ShiftTemplate.DAY)
    care_session = await CareSessionService(session).create_request(requester, provider.id, CARE_DATE, 14, 20)

    rejected = await CareSessionService(session).reject(care_session.id, provider)
    assert rejected.status == CareSessionStatus.REJECTED

    reapplied = await CareSessionService(session).create_request(requester, provider.id, CARE_DATE, 14, 20)
    assert reapplied.id != care_session.id
    assert reapplied.status == CareSessionStatus.REQUESTED
