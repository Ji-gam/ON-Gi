"""REQ-F-ACC-07/08/10: 8문항 응답으로 온기·통제 점수와 유형이 산출되고, 재진단·자유서술 제출마다
이력이 남아야 한다."""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.baumrind_questions import ParentingTypeLabel
from app.models.base import Base
from app.models.parenting_values import ParentingValuesHistory, ParentingValuesSource
from app.services.parenting_values_service import ParentingValuesService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES

HIGH_WARMTH_HIGH_CONTROL = [5, 5, 5, 5, 5, 5, 5, 5]
LOW_WARMTH_LOW_CONTROL = [1, 1, 1, 1, 1, 1, 1, 1]


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)()


async def _signed_up_user(session, *, email: str, nickname: str, phone: str):
    agreements = [
        TermAgreementItem(terms_type=t, version=CATALOG_BY_TYPE[t].version, agreed=True) for t in REQUIRED_TYPES
    ]
    result = await AuthService(session).signup(
        SignUpRequest(
            email=email,
            password="Password123!",
            name="홍길동",
            nickname=nickname,
            birth_date=date(1990, 1, 1),
            gender=Gender.MALE,
            phone_number=phone,
            agreements=agreements,
        )
    )
    return result.user


async def test_invalid_answer_range_is_rejected():
    session = await _session()
    user = await _signed_up_user(session, email="a@example.com", nickname="보호자1", phone="010-1111-1111")

    with pytest.raises(HTTPException) as exc:
        await ParentingValuesService(session).submit_questionnaire(user, [0, 5, 5, 5, 5, 5, 5, 5])
    assert exc.value.status_code == 400


async def test_questionnaire_computes_scores_and_type_label():
    session = await _session()
    user = await _signed_up_user(session, email="b@example.com", nickname="보호자2", phone="010-2222-2222")

    profile = await ParentingValuesService(session).submit_questionnaire(user, HIGH_WARMTH_HIGH_CONTROL)
    assert profile.warmth_score == 5.0
    assert profile.control_score == 5.0
    assert profile.type_label == ParentingTypeLabel.AUTHORITATIVE

    profile2 = await ParentingValuesService(session).submit_questionnaire(user, LOW_WARMTH_LOW_CONTROL)
    assert profile2.user_id == profile.user_id
    assert profile2.type_label == ParentingTypeLabel.NEGLECTFUL

    history = (await session.execute(ParentingValuesHistory.__table__.select())).fetchall()
    assert len(history) == 2


async def test_narrative_requires_prior_questionnaire():
    session = await _session()
    user = await _signed_up_user(session, email="c@example.com", nickname="보호자3", phone="010-3333-3333")

    with pytest.raises(HTTPException) as exc:
        await ParentingValuesService(session).submit_narrative(user, "아이와 매일 대화하려 노력합니다.")
    assert exc.value.status_code == 400


async def test_narrative_is_stored_and_logs_history():
    session = await _session()
    user = await _signed_up_user(session, email="d@example.com", nickname="보호자4", phone="010-4444-4444")
    await ParentingValuesService(session).submit_questionnaire(user, HIGH_WARMTH_HIGH_CONTROL)

    profile = await ParentingValuesService(session).submit_narrative(user, "아이와 매일 대화하려 노력합니다.")
    assert profile.narrative == "아이와 매일 대화하려 노력합니다."

    history = (
        await session.execute(
            ParentingValuesHistory.__table__.select().where(
                ParentingValuesHistory.source == ParentingValuesSource.NARRATIVE
            )
        )
    ).fetchall()
    assert len(history) == 1


async def test_get_profile_without_diagnosis_is_404():
    session = await _session()
    user = await _signed_up_user(session, email="e@example.com", nickname="보호자5", phone="010-5555-5555")

    with pytest.raises(HTTPException) as exc:
        await ParentingValuesService(session).get_profile(user)
    assert exc.value.status_code == 404
