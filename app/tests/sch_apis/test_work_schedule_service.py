"""REQ-F-SCH-01/03/06: 근무 템플릿 등록 시 48슬롯 비트마스크가 올바르게 계산되고,
자정을 넘기는 NIGHT 근무는 당일+익일 양쪽에 걸쳐 반영되어야 한다."""

from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.utils.schedule_slots import ShiftTemplate
from app.models.base import Base
from app.services.work_schedule_service import WorkScheduleService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES


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


async def test_day_shift_masks_07_to_15():
    session = await _session()
    user = await _signed_up_user(session, email="a@example.com", nickname="근무자1", phone="010-1111-1111")

    rows = await WorkScheduleService(session).register_shift(user, date(2026, 8, 12), ShiftTemplate.DAY)
    assert len(rows) == 1
    mask = rows[0].slot_bitmask
    for idx in range(14, 30):
        assert (mask >> idx) & 1 == 0
    assert (mask >> 13) & 1 == 1
    assert (mask >> 30) & 1 == 1


async def test_night_shift_splits_across_two_days():
    session = await _session()
    user = await _signed_up_user(session, email="b@example.com", nickname="근무자2", phone="010-2222-2222")

    rows = await WorkScheduleService(session).register_shift(user, date(2026, 8, 12), ShiftTemplate.NIGHT)
    assert len(rows) == 2
    today, tomorrow = rows
    assert today.work_date == date(2026, 8, 12)
    assert tomorrow.work_date == date(2026, 8, 13)
    for idx in (46, 47):
        assert (today.slot_bitmask >> idx) & 1 == 0
    for idx in range(14):
        assert (tomorrow.slot_bitmask >> idx) & 1 == 0
    assert (tomorrow.slot_bitmask >> 14) & 1 == 1


async def test_day_and_evening_shift_produce_16_complementary_slots_each():
    from app.core.utils.schedule_slots import complementary_slot_counts, template_masks

    day_mask, _ = template_masks(ShiftTemplate.DAY)
    evening_mask, _ = template_masks(ShiftTemplate.EVENING)
    day_needs_evening, evening_needs_day = complementary_slot_counts(day_mask, evening_mask)
    assert day_needs_evening == 16
    assert evening_needs_day == 16


async def test_list_range_returns_registered_dates_in_order():
    session = await _session()
    user = await _signed_up_user(session, email="c@example.com", nickname="근무자3", phone="010-3333-3333")

    service = WorkScheduleService(session)
    await service.register_shift(user, date(2026, 8, 10), ShiftTemplate.DAY)
    await service.register_shift(user, date(2026, 8, 12), ShiftTemplate.EVENING)

    rows = await service.list_range(user, date(2026, 8, 1), date(2026, 8, 31))
    assert [r.work_date for r in rows] == [date(2026, 8, 10), date(2026, 8, 12)]
