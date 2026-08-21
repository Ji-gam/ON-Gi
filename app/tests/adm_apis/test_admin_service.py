"""REQ-F-ADM-02(핵심 지표 집계)/ADM-03(접근 로그)/ADM-05(아동 안전 긴급 정지)."""

from datetime import date

import h3
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.access_log import AccessAction, AccessLog
from app.models.base import Base
from app.models.care_session import CareSessionStatus
from app.models.children import ChildGender
from app.models.guardian_profile import HouseholdComposition, JobCategory, WorkType
from app.models.point_hold import PointHoldStatus
from app.repositories.point_hold_repository import PointHoldRepository
from app.services.admin_service import ADMIN_ONLY_MESSAGE, AdminMetricsService, AdminSuspendService
from app.services.care_session_service import CareSessionService
from app.services.child_service import ChildService
from app.services.guardian_profile_service import GuardianProfileService
from app.services.matching_service import MatchingService
from app.services.notification_service import NotificationService
from app.services.parenting_values_service import ParentingValuesService
from app.services.point_ledger_service import PointLedgerService
from app.services.trust_evaluation_service import TrustEvaluationService
from app.services.work_schedule_service import WorkScheduleService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES, TermsType

SEOUL_H3 = h3.latlng_to_cell(37.5665, 126.9780, 9)
NEARBY_H3 = h3.latlng_to_cell(37.5665, 126.9830, 9)
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


async def _guardian_pair(session):
    a = await _signed_up_user(session, email="adm_svc_a@example.com", nickname="관리자시험A", phone="010-9401-0001")
    b = await _signed_up_user(session, email="adm_svc_b@example.com", nickname="관리자시험B", phone="010-9401-0002")

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
    return a, b


async def test_access_log_recorded_on_child_create_and_view():
    session = await _session()
    parent = await _signed_up_user(
        session, email="acc_log_parent@example.com", nickname="접근로그부모", phone="010-9401-0010"
    )

    child = await ChildService(session).create_child(
        parent,
        months_old=12,
        gender=ChildGender.MALE,
        temperament_memo=None,
        allergies="땅콩",
        conditions=None,
        medications=None,
    )
    await ChildService(session).get_child(parent, child.id)

    logs = (await session.execute(select(AccessLog).where(AccessLog.target_child_id == child.id))).scalars().all()
    actions = {log.action for log in logs}
    assert actions == {AccessAction.EDIT, AccessAction.VIEW}
    assert all(log.actor_user_id == parent.id for log in logs)


async def test_core_metrics_computed_from_hypothesis_events():
    session = await _session()
    a, b = await _guardian_pair(session)
    child_a = await ChildService(session).create_child(
        a,
        months_old=12,
        gender=ChildGender.MALE,
        temperament_memo=None,
        allergies=None,
        conditions=None,
        medications=None,
    )

    await MatchingService(session).find_candidates(a, FOR_DATE)

    first = await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 14, 20)
    await CareSessionService(session).accept(first.id, b)
    checked_in = await CareSessionService(session).checkin(first.id, b, *h3.cell_to_latlng(SEOUL_H3), None)
    completed = await CareSessionService(session).checkout(checked_in.id, b)
    await TrustEvaluationService(session).submit(completed.id, a, rating=5, tags=[])
    await TrustEvaluationService(session).submit(completed.id, b, rating=5, tags=[])

    # 두 번째 요청은 완료 이력이 있는 상대라 REMATCH_REQUESTED로 적재된다.
    await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 20, 24)

    metrics = await AdminMetricsService(session).get_core_metrics()

    assert metrics["candidate_availability_rate"] == pytest.approx(0.5)  # a만 노출됨 / 전체 2명
    assert metrics["l2_to_l3_transition_rate"] == pytest.approx(0.0)  # L2까지만 도달, L3 미도달
    assert metrics["rematch_rate"] == pytest.approx(0.5)  # REQUEST_CREATED 1 + REMATCH_REQUESTED 1


async def test_emergency_suspend_requires_admin():
    session = await _session()
    a, b = await _guardian_pair(session)

    with pytest.raises(HTTPException) as exc_info:
        await AdminSuspendService(session).emergency_suspend(a, b.id, "테스트")
    assert exc_info.value.detail == ADMIN_ONLY_MESSAGE


async def test_emergency_suspend_cancels_active_sessions_and_refunds_hold():
    session = await _session()
    a, b = await _guardian_pair(session)
    child_a = await ChildService(session).create_child(
        a,
        months_old=12,
        gender=ChildGender.MALE,
        temperament_memo=None,
        allergies=None,
        conditions=None,
        medications=None,
    )
    admin = await _signed_up_user(
        session, email="adm_svc_admin@example.com", nickname="관리자시험운영", phone="010-9401-0099", is_admin=True
    )

    care_session = await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 14, 20)
    await CareSessionService(session).accept(care_session.id, b)  # CONFIRMED + 홀드 생성

    stopped = await AdminSuspendService(session).emergency_suspend(admin, b.id, "아동 안전 신고 접수")

    assert len(stopped) == 1
    await session.refresh(care_session)
    assert care_session.status == CareSessionStatus.CANCELLED
    assert "긴급 정지" in care_session.cancel_reason

    await session.refresh(b)
    assert b.is_sanctioned is True
    assert b.is_active is False

    hold = await PointHoldRepository(session).get_by_care_session(care_session.id)
    assert hold.status == PointHoldStatus.RELEASED
    assert await PointLedgerService(session).get_held_balance(a.id) == 0

    notifications = await NotificationService(session).list_notifications(a.id)
    assert any(n.payload and n.payload.get("session_id") == care_session.id for n in notifications)
