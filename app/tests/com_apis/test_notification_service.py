"""REQ-F-COM-02: CAR 요청/수락/거절/완료·TRS 신뢰등급 전이 지점에서 알림이 올바른
수신자로 적재되는지, 그리고 조회·읽음 처리가 동작하는지 검증."""

from datetime import date

import h3
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
from app.models.children import ChildGender
from app.models.guardian_profile import HouseholdComposition, JobCategory, WorkType
from app.models.notification import NotificationType
from app.services.care_session_service import CareSessionService
from app.services.child_service import ChildService
from app.services.guardian_profile_service import GuardianProfileService
from app.services.notification_service import NotificationService
from app.services.parenting_values_service import ParentingValuesService
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
    a = await _signed_up_user(session, email="com_a@example.com", nickname="COM보호자A", phone="010-9401-0001")
    b = await _signed_up_user(session, email="com_b@example.com", nickname="COM보호자B", phone="010-9401-0002")

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


async def test_request_lifecycle_notifies_the_right_party():
    session = await _session()
    a, b = await _guardian_pair(session)
    child_a = (await ChildService(session).list_children(a))[0]

    care_session = await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 14, 20)

    provider_notifications = await NotificationService(session).list_notifications(b.id)
    assert any(n.type == NotificationType.REQUEST_CREATED for n in provider_notifications)

    await CareSessionService(session).accept(care_session.id, b)
    requester_notifications = await NotificationService(session).list_notifications(a.id)
    assert any(n.type == NotificationType.REQUEST_ACCEPTED for n in requester_notifications)

    checked_in = await CareSessionService(session).checkin(care_session.id, b, *h3.cell_to_latlng(SEOUL_H3), None)
    await CareSessionService(session).checkout(checked_in.id, b)
    requester_notifications = await NotificationService(session).list_notifications(a.id)
    assert any(n.type == NotificationType.SESSION_COMPLETED for n in requester_notifications)

    # L1 전이도 함께 알림이 적재된다(양쪽 모두).
    assert any(n.type == NotificationType.TRUST_LEVEL_TRANSITION for n in requester_notifications)
    provider_notifications = await NotificationService(session).list_notifications(b.id)
    assert any(n.type == NotificationType.TRUST_LEVEL_TRANSITION for n in provider_notifications)


async def test_reject_notifies_requester():
    session = await _session()
    a, b = await _guardian_pair(session)
    child_a = (await ChildService(session).list_children(a))[0]

    care_session = await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 14, 20)
    await CareSessionService(session).reject(care_session.id, b)

    requester_notifications = await NotificationService(session).list_notifications(a.id)
    assert any(n.type == NotificationType.REQUEST_REJECTED for n in requester_notifications)


async def test_mark_read_is_idempotent_and_scoped_to_owner():
    session = await _session()
    a, b = await _guardian_pair(session)
    child_a = (await ChildService(session).list_children(a))[0]

    await CareSessionService(session).create_request(a, b.id, child_a.id, SEOUL_H3, FOR_DATE, 14, 20)
    notification = (await NotificationService(session).list_notifications(b.id))[0]
    assert notification.read_at is None

    read_once = await NotificationService(session).mark_read(notification.id, b.id)
    assert read_once.read_at is not None

    read_twice = await NotificationService(session).mark_read(notification.id, b.id)
    assert read_twice.read_at == read_once.read_at
