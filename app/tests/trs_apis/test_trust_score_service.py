"""REQ-F-TRS-06/08: 신뢰 점수는 가중합으로 산출되고, 가중치는 운영자만 변경할 수 있으며
변경 시 이력이 남는다."""

from datetime import date, timedelta

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
from app.services.trust_score_service import TrustScoreService
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


async def test_score_is_neutral_for_new_user_with_no_history():
    session = await _session()
    user = await _signed_up_user(session, email="s1@example.com", nickname="점수1", phone="010-9101-0001")

    score = await TrustScoreService(session).calculate_score(user.id)
    # w1*0.5 + w2*1.0 + w3*1.0 + w4*1.0, 기본 가중치 합=1.0인 상태에서 0.5~1.0 사이 중립값
    assert 0.5 <= score <= 1.0


async def test_update_weights_requires_admin_and_sum_to_one():
    session = await _session()
    admin = await _signed_up_user(
        session, email="s2@example.com", nickname="점수관리자", phone="010-9102-0001", is_admin=True
    )
    non_admin = await _signed_up_user(session, email="s2b@example.com", nickname="점수비관리자", phone="010-9102-0002")

    with pytest.raises(HTTPException) as exc:
        await TrustScoreService(session).update_weights(non_admin, 0.5, 0.2, 0.2, 0.1)
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        await TrustScoreService(session).update_weights(admin, 0.5, 0.2, 0.2, 0.2)
    assert exc.value.status_code == 400

    updated = await TrustScoreService(session).update_weights(admin, 0.5, 0.2, 0.2, 0.1)
    assert updated.w1 == 0.5


async def test_weight_change_records_history_with_previous_values():
    session = await _session()
    admin = await _signed_up_user(
        session, email="s3@example.com", nickname="점수관리자3", phone="010-9103-0001", is_admin=True
    )

    from sqlalchemy import select

    from app.models.trust_weights import TrustWeightHistory

    await TrustScoreService(session).update_weights(admin, 0.5, 0.2, 0.2, 0.1)
    result = await session.execute(select(TrustWeightHistory))
    history_rows = list(result.scalars().all())
    assert len(history_rows) == 1
    assert history_rows[0].previous_w1 == 0.4
    assert history_rows[0].changed_by_user_id == admin.id


async def test_score_reflects_rating_and_journal_completion():
    session = await _session()
    requester = await _signed_up_user(
        session, email="s4_req@example.com", nickname="점수요청자4", phone="010-9104-0001"
    )
    provider = await _signed_up_user(
        session, email="s4_prov@example.com", nickname="점수제공자4", phone="010-9104-0002"
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
    care_session = await CareSessionService(session).create_request(
        requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
    )
    confirmed = await CareSessionService(session).accept(care_session.id, provider)
    await CareSessionService(session).checkin(confirmed.id, provider, MEETING_LAT, MEETING_LNG, None)
    completed = await CareSessionService(session).checkout(confirmed.id, provider)

    before = await TrustScoreService(session).calculate_score(provider.id)

    await TrustEvaluationService(session).submit(completed.id, requester, 5, ["시간 준수"])
    after_rating = await TrustScoreService(session).calculate_score(provider.id)
    assert after_rating > before  # 별점 5는 중립값(3점 상당)보다 높아 점수가 오른다


async def test_no_show_lowers_at_fault_users_score_only():
    session = await _session()
    requester = await _signed_up_user(
        session, email="s5_req@example.com", nickname="점수요청자5", phone="010-9105-0001"
    )
    provider = await _signed_up_user(
        session, email="s5_prov@example.com", nickname="점수제공자5", phone="010-9105-0002"
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
    care_session = await CareSessionService(session).create_request(
        requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
    )
    confirmed = await CareSessionService(session).accept(care_session.id, provider)
    confirmed.care_date = date.today() - timedelta(days=1)
    await session.commit()

    requester_score_before = await TrustScoreService(session).calculate_score(requester.id)
    provider_score_before = await TrustScoreService(session).calculate_score(provider.id)

    await CareSessionService(session).report_no_show(confirmed.id, provider, "요청자가 아이를 데려오지 않음")

    requester_score_after = await TrustScoreService(session).calculate_score(requester.id)
    provider_score_after = await TrustScoreService(session).calculate_score(provider.id)

    assert requester_score_after < requester_score_before
    assert provider_score_after == provider_score_before
