"""REQ-F-TRS-01/02/03/04: 신뢰 등급 상태머신 L1→L2→L3, 공동육아 일정으로 승급, 강등은
운영자만 가능."""

from datetime import date

import h3
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
from app.models.children import ChildGender
from app.models.joint_care_session import JointCareSessionStatus
from app.models.trust_level import TrustLevel
from app.services.care_session_service import CareSessionService
from app.services.child_service import ChildService
from app.services.trust_level_service import TrustLevelService
from app.services.work_schedule_service import WorkScheduleService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES, TermsType

CARE_DATE = date(2026, 8, 12)
MEETING_H3 = h3.latlng_to_cell(37.5665, 126.9780, 9)


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


async def _signed_up_user(session, *, email: str, nickname: str, phone: str, is_admin: bool = False):
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
    user = result.user
    if is_admin:
        user.is_admin = True
        await session.commit()
        await session.refresh(user)
    return user


async def _confirmed_relationship_pair(session):
    """돌봄 요청 생성+수락으로 L1 관계를 맺은 requester/provider를 반환."""
    requester = await _signed_up_user(session, email="l1_req@example.com", nickname="관계요청자", phone="010-9201-0001")
    provider = await _signed_up_user(session, email="l1_prov@example.com", nickname="관계제공자", phone="010-9201-0002")

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
    await CareSessionService(session).accept(care_session.id, provider)
    return requester, provider


async def test_accept_grants_l1_relationship():
    session = await _session()
    requester, provider = await _confirmed_relationship_pair(session)

    relationship = await TrustLevelService(session).get_relationship(requester.id, provider.id)
    assert relationship is not None
    assert relationship.level == TrustLevel.L1
    assert relationship.joint_session_count == 0


async def test_solo_request_blocked_before_l3():
    session = await _session()
    requester, provider = await _confirmed_relationship_pair(session)

    child2 = await ChildService(session).create_child(
        requester,
        months_old=6,
        gender=ChildGender.FEMALE,
        temperament_memo=None,
        allergies=None,
        conditions=None,
        medications=None,
    )
    with pytest.raises(HTTPException) as exc:
        await CareSessionService(session).create_request(
            requester, provider.id, child2.id, MEETING_H3, CARE_DATE, 20, 24, is_solo=True
        )
    assert exc.value.status_code == 403

    # 일반(비-단독) 재요청은 REQ-F-MAT-09에 따라 L3 이전에도 허용된다.
    non_solo = await CareSessionService(session).create_request(
        requester, provider.id, child2.id, MEETING_H3, CARE_DATE, 20, 24
    )
    assert non_solo is not None


async def test_joint_session_registration_transitions_l1_to_l2():
    session = await _session()
    requester, provider = await _confirmed_relationship_pair(session)

    joint = await TrustLevelService(session).schedule_joint_session(
        requester, provider.id, "동네 키즈카페", date(2026, 8, 20)
    )
    assert joint.status == JointCareSessionStatus.SCHEDULED

    relationship = await TrustLevelService(session).get_relationship(requester.id, provider.id)
    assert relationship.level == TrustLevel.L2


async def test_confirm_by_both_sides_accumulates_and_unlocks_l3_at_required_count():
    session = await _session()
    requester, provider = await _confirmed_relationship_pair(session)
    service = TrustLevelService(session)

    await service.set_required_count(requester, 2)
    await service.set_required_count(provider, 2)

    for day in (20, 21):
        joint = await service.schedule_joint_session(requester, provider.id, "공원", date(2026, 8, day))
        await service.confirm_joint_session(joint.id, requester)
        confirmed = await service.confirm_joint_session(joint.id, provider)
        assert confirmed.status == JointCareSessionStatus.COMPLETED

    relationship = await service.get_relationship(requester.id, provider.id)
    assert relationship.joint_session_count == 2
    assert relationship.level == TrustLevel.L3

    # L3 도달 후에는 단독 위탁 요청도 허용된다.
    child2 = await ChildService(session).create_child(
        requester,
        months_old=6,
        gender=ChildGender.FEMALE,
        temperament_memo=None,
        allergies=None,
        conditions=None,
        medications=None,
    )
    care_session = await CareSessionService(session).create_request(
        requester, provider.id, child2.id, MEETING_H3, CARE_DATE, 20, 24, is_solo=True
    )
    assert care_session is not None


async def test_confirm_by_non_participant_is_forbidden():
    session = await _session()
    requester, provider = await _confirmed_relationship_pair(session)
    outsider = await _signed_up_user(session, email="outsider@example.com", nickname="외부인", phone="010-9201-0003")

    joint = await TrustLevelService(session).schedule_joint_session(requester, provider.id, "공원", date(2026, 8, 20))
    with pytest.raises(HTTPException) as exc:
        await TrustLevelService(session).confirm_joint_session(joint.id, outsider)
    assert exc.value.status_code == 403


async def test_solo_request_blocked_without_any_relationship():
    session = await _session()
    requester = await _signed_up_user(
        session, email="nosolo_a@example.com", nickname="단독요청자", phone="010-9201-0008"
    )
    provider = await _signed_up_user(
        session, email="nosolo_b@example.com", nickname="단독제공자", phone="010-9201-0009"
    )
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
            requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20, is_solo=True
        )
    assert exc.value.status_code == 403


async def test_schedule_joint_session_requires_existing_relationship():
    session = await _session()
    a = await _signed_up_user(session, email="norel_a@example.com", nickname="무관계1", phone="010-9201-0004")
    b = await _signed_up_user(session, email="norel_b@example.com", nickname="무관계2", phone="010-9201-0005")

    with pytest.raises(HTTPException) as exc:
        await TrustLevelService(session).schedule_joint_session(a, b.id, "공원", date(2026, 8, 20))
    assert exc.value.status_code == 404


async def test_set_required_count_rejects_below_minimum():
    session = await _session()
    requester, _provider = await _confirmed_relationship_pair(session)

    with pytest.raises(HTTPException) as exc:
        await TrustLevelService(session).set_required_count(requester, 0)
    assert exc.value.status_code == 400


async def test_demote_requires_admin_and_records_history():
    session = await _session()
    requester, provider = await _confirmed_relationship_pair(session)
    service = TrustLevelService(session)
    await service.set_required_count(requester, 1)
    await service.set_required_count(provider, 1)
    joint = await service.schedule_joint_session(requester, provider.id, "공원", date(2026, 8, 20))
    await service.confirm_joint_session(joint.id, requester)
    await service.confirm_joint_session(joint.id, provider)

    relationship = await service.get_relationship(requester.id, provider.id)
    assert relationship.level == TrustLevel.L3

    non_admin = await _signed_up_user(session, email="nonadmin@example.com", nickname="비관리자", phone="010-9201-0006")
    with pytest.raises(HTTPException) as exc:
        await service.demote(non_admin, requester.id, provider.id, "신고 접수")
    assert exc.value.status_code == 403

    admin = await _signed_up_user(
        session, email="trsadmin@example.com", nickname="TRS관리자", phone="010-9201-0007", is_admin=True
    )
    demoted = await service.demote(admin, requester.id, provider.id, "신고 접수")
    assert demoted.level == TrustLevel.L2

    from sqlalchemy import select

    from app.models.trust_level import TrustLevelHistory

    result = await session.execute(select(TrustLevelHistory).where(TrustLevelHistory.reason == "신고 접수"))
    history = result.scalar_one()
    assert history.previous_level == TrustLevel.L3
    assert history.new_level == TrustLevel.L2
    assert history.changed_by_user_id == admin.id
