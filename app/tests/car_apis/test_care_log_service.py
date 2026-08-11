"""REQ-F-CAR-06: 돌봄 일지는 세션당 1건(upsert)이며, 알레르기 등록 아동은 알레르기 항목
미입력 시 저장이 거부된다."""

from datetime import date

import h3
import pytest
from fastapi import HTTPException

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.children import ChildGender
from app.services.care_log_service import CareLogService
from app.services.care_session_service import CareSessionService
from app.services.child_service import ChildService
from app.services.work_schedule_service import WorkScheduleService
from app.tests.car_apis.test_care_session_service import _session, _signed_up_user

CARE_DATE = date(2026, 8, 12)
MEETING_H3 = h3.latlng_to_cell(37.5665, 126.9780, 9)


async def _confirmed_session_with_child(session, *, allergies: str | None):
    requester = await _signed_up_user(
        session, email="log_req@example.com", nickname="일지요청자", phone="010-8000-0001"
    )
    provider = await _signed_up_user(
        session, email="log_prov@example.com", nickname="일지제공자", phone="010-8000-0002"
    )
    child = await ChildService(session).create_child(
        requester,
        months_old=12,
        gender=ChildGender.MALE,
        temperament_memo=None,
        allergies=allergies,
        conditions=None,
        medications=None,
    )
    await WorkScheduleService(session).register_shift(requester, CARE_DATE, ShiftTemplate.DAY)
    care_session = await CareSessionService(session).create_request(
        requester, provider.id, child.id, MEETING_H3, CARE_DATE, 14, 20
    )
    confirmed = await CareSessionService(session).accept(care_session.id, provider)
    return confirmed, requester, provider


async def test_upsert_rejects_missing_allergy_note_for_allergic_child():
    session = await _session()
    confirmed, _requester, provider = await _confirmed_session_with_child(session, allergies="땅콩")

    with pytest.raises(HTTPException) as exc:
        await CareLogService(session).upsert(
            confirmed.id, provider, meal="점심", sleep="1시간", mood="좋음", note=None, allergy_note=None
        )
    assert exc.value.status_code == 400

    saved = await CareLogService(session).upsert(
        confirmed.id, provider, meal="점심", sleep="1시간", mood="좋음", note=None, allergy_note="견과류 제외 식단 제공"
    )
    assert saved.allergy_note == "견과류 제외 식단 제공"


async def test_upsert_allows_missing_allergy_note_for_non_allergic_child():
    session = await _session()
    confirmed, _requester, provider = await _confirmed_session_with_child(session, allergies=None)

    saved = await CareLogService(session).upsert(
        confirmed.id, provider, meal="점심", sleep="1시간", mood="좋음", note=None, allergy_note=None
    )
    assert saved.meal == "점심"


async def test_upsert_is_idempotent_per_session_and_only_provider_can_write():
    session = await _session()
    confirmed, requester, provider = await _confirmed_session_with_child(session, allergies=None)

    with pytest.raises(HTTPException) as exc:
        await CareLogService(session).upsert(
            confirmed.id, requester, meal="점심", sleep=None, mood=None, note=None, allergy_note=None
        )
    assert exc.value.status_code == 404

    first = await CareLogService(session).upsert(
        confirmed.id, provider, meal="점심", sleep=None, mood=None, note=None, allergy_note=None
    )
    second = await CareLogService(session).upsert(
        confirmed.id, provider, meal="저녁", sleep=None, mood=None, note=None, allergy_note=None
    )
    assert first.session_id == second.session_id
    assert second.meal == "저녁"


async def test_requester_can_read_but_not_write_journal():
    session = await _session()
    confirmed, requester, provider = await _confirmed_session_with_child(session, allergies=None)
    await CareLogService(session).upsert(
        confirmed.id, provider, meal="점심", sleep=None, mood=None, note=None, allergy_note=None
    )

    read_by_requester = await CareLogService(session).get(confirmed.id, requester)
    assert read_by_requester is not None
    assert read_by_requester.meal == "점심"
