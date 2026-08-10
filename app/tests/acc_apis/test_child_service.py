"""REQ-F-ACC-03/05/06: 아동 등록은 법정대리인 동의가 먼저 있어야 하고, 본인 소유 아동만
조회·삭제할 수 있어야 한다."""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.children import ChildGender
from app.services.child_service import ChildService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES, TermsType


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)()


def _agreements(*, guardian_consent: bool = False) -> list[TermAgreementItem]:
    items = [TermAgreementItem(terms_type=t, version=CATALOG_BY_TYPE[t].version, agreed=True) for t in REQUIRED_TYPES]
    items.append(
        TermAgreementItem(
            terms_type=str(TermsType.GUARDIAN_CONSENT),
            version=CATALOG_BY_TYPE[str(TermsType.GUARDIAN_CONSENT)].version,
            agreed=guardian_consent,
        )
    )
    return items


async def _signed_up_user(session, *, email: str, nickname: str, phone: str, guardian_consent: bool = False):
    result = await AuthService(session).signup(
        SignUpRequest(
            email=email,
            password="Password123!",
            name="홍길동",
            nickname=nickname,
            birth_date=date(1990, 1, 1),
            gender=Gender.MALE,
            phone_number=phone,
            agreements=_agreements(guardian_consent=guardian_consent),
        )
    )
    return result.user


async def test_create_child_without_guardian_consent_is_rejected():
    session = await _session()
    user = await _signed_up_user(session, email="a@example.com", nickname="보호자1", phone="010-1111-1111")

    with pytest.raises(HTTPException) as exc:
        await ChildService(session).create_child(
            user,
            months_old=14,
            gender=ChildGender.FEMALE,
            temperament_memo=None,
            allergies=None,
            conditions=None,
            medications=None,
        )
    assert exc.value.status_code == 400


async def test_create_child_with_guardian_consent_stores_sensitive_info_separately():
    session = await _session()
    user = await _signed_up_user(
        session, email="b@example.com", nickname="보호자2", phone="010-2222-2222", guardian_consent=True
    )

    child = await ChildService(session).create_child(
        user,
        months_old=18,
        gender=ChildGender.MALE,
        temperament_memo="낯을 가림",
        allergies="땅콩",
        conditions=None,
        medications=None,
    )

    assert child.user_id == user.id
    assert child.has_sensitive_info is True
    fetched = await ChildService(session).get_child(user, child.id)
    assert fetched.sensitive.allergies == "땅콩"


async def test_child_ownership_is_enforced():
    session = await _session()
    owner = await _signed_up_user(
        session, email="c@example.com", nickname="보호자3", phone="010-3333-3333", guardian_consent=True
    )
    stranger = await _signed_up_user(
        session, email="d@example.com", nickname="보호자4", phone="010-4444-4444", guardian_consent=True
    )

    child = await ChildService(session).create_child(
        owner,
        months_old=6,
        gender=ChildGender.FEMALE,
        temperament_memo=None,
        allergies=None,
        conditions=None,
        medications=None,
    )

    with pytest.raises(HTTPException) as exc:
        await ChildService(session).get_child(stranger, child.id)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        await ChildService(session).delete_child(stranger, child.id)
    assert exc.value.status_code == 404

    # 소유자 본인은 삭제할 수 있다.
    await ChildService(session).delete_child(owner, child.id)
    assert await ChildService(session).list_children(owner) == []
